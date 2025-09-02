import os
import sqlite3
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import requests
from dotenv import load_dotenv
import csv
import io

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# SecurityTrails API configuration
API_KEY = os.getenv('SECURITYTRAILS_API_KEY')
API_BASE_URL = 'https://api.securitytrails.com/v1'

# Database configuration
DATABASE = 'domains.db'

def init_db():
    """Initialize the SQLite database with required tables and indexes."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create domains table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            mx TEXT,
            ns TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(domain, mx, ns)
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mx ON domains(mx)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ns ON domains(ns)')
    
    conn.commit()
    conn.close()

def check_cache(record_type, host):
    """Check if we have cached data for the given type and host."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    if record_type == 'mx':
        cursor.execute('SELECT COUNT(*) FROM domains WHERE mx = ?', (host,))
    else:  # ns
        cursor.execute('SELECT COUNT(*) FROM domains WHERE ns = ?', (host,))
    
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def insert_into_sqlite(domain, mx=None, ns=None):
    """Insert a domain record into SQLite, skipping duplicates."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO domains (domain, mx, ns, fetched_at)
            VALUES (?, ?, ?, ?)
        ''', (domain, mx, ns, datetime.now()))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def query_sqlite(record_type, host, page=1, limit=50):
    """Query SQLite for paginated results."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    offset = (page - 1) * limit
    
    if record_type == 'mx':
        cursor.execute('''
            SELECT domain, mx, ns, fetched_at FROM domains 
            WHERE mx = ? 
            ORDER BY fetched_at DESC 
            LIMIT ? OFFSET ?
        ''', (host, limit, offset))
    else:  # ns
        cursor.execute('''
            SELECT domain, mx, ns, fetched_at FROM domains 
            WHERE ns = ? 
            ORDER BY fetched_at DESC 
            LIMIT ? OFFSET ?
        ''', (host, limit, offset))
    
    results = cursor.fetchall()
    
    # Get total count for pagination
    if record_type == 'mx':
        cursor.execute('SELECT COUNT(*) FROM domains WHERE mx = ?', (host,))
    else:
        cursor.execute('SELECT COUNT(*) FROM domains WHERE ns = ?', (host,))
    
    total_count = cursor.fetchone()[0]
    conn.close()
    
    return results, total_count

def query_all_sqlite(record_type, host):
    """Query all records for CSV export."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    if record_type == 'mx':
        cursor.execute('''
            SELECT domain, mx, ns, fetched_at FROM domains 
            WHERE mx = ? 
            ORDER BY fetched_at DESC
        ''', (host,))
    else:  # ns
        cursor.execute('''
            SELECT domain, mx, ns, fetched_at FROM domains 
            WHERE ns = ? 
            ORDER BY fetched_at DESC
        ''', (host,))
    
    results = cursor.fetchall()
    conn.close()
    return results

def test_api_connection():
    """Test API connection and authentication."""
    if not API_KEY:
        return False, "API key not configured"
    
    headers = {
        'APIKEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        # Test with ping endpoint first
        ping_url = f"{API_BASE_URL}/ping"
        response = requests.get(ping_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return True, "API connection successful"
        else:
            return False, f"API ping failed: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"API connection error: {str(e)}"

def fetch_reverse_records_with_scroll(record_type, host):
    """Fetch reverse records using DSL API with scroll for unlimited results."""
    if not API_KEY:
        flash('SecurityTrails API key not configured', 'error')
        return
    
    headers = {
        'APIKEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    new_records = 0
    
    # Try multiple DSL endpoints
    dsl_endpoints = [
        f"{API_BASE_URL}/search/list",         # From documentation examples
        f"{API_BASE_URL}/domains/list-backup"  # From API reference
    ]
    
    # Construct proper DSL query syntax
    if record_type == 'mx':
        dsl_query = f"mx = '{host}'"
    else:  # ns
        dsl_query = f"ns = '{host}'"
    
    request_body = {
        'query': dsl_query,
        'scroll': True,
        'include_inactive': False
    }
    
    print(f"Trying DSL API with query: {dsl_query}")
    
    # Try each endpoint until one works
    for endpoint_url in dsl_endpoints:
        try:
            print(f"Trying DSL endpoint: {endpoint_url}")
            
            time.sleep(0.2)
            response = requests.post(endpoint_url, headers=headers, json=request_body, timeout=30)
            
            print(f"DSL Response status: {response.status_code}")
            
            if response.status_code == 404:
                print(f"Endpoint {endpoint_url} not found, trying next...")
                continue
            elif response.status_code != 200:
                error_msg = f'DSL API Error: {response.status_code} - {response.text}'
                print(error_msg)
                continue
            
            # Success! Process the response
            data = response.json()
            print(f"DSL Response keys: {list(data.keys())}")
            
            records = data.get('records', [])
            scroll_id = data.get('scroll_id')
            meta = data.get('meta', {})
            
            print(f"DSL first batch: {len(records)} records")
            print(f"Scroll ID: {scroll_id}")
            print(f"Meta info: {meta}")
            
            # Insert records
            for record in records:
                domain = record.get('hostname', '')
                if domain:
                    if record_type == 'mx':
                        insert_into_sqlite(domain, mx=host, ns=None)
                    else:
                        insert_into_sqlite(domain, mx=None, ns=host)
                    new_records += 1
            
            # Check if there are more results available
            total_records = meta.get('total_records', 0)
            print(f"Total available records according to meta: {total_records}")
            
            # Continue with scroll if available and there are more records
            if scroll_id and total_records > len(records):
                print(f"Starting scroll to fetch {total_records - len(records)} more records...")
                batch_count = 1
                
                while scroll_id and batch_count < 500:  # Increased limit for large datasets
                    print(f"DSL scroll batch {batch_count + 1}...")
                    
                    time.sleep(0.2)
                    
                    scroll_url = f"{API_BASE_URL}/scroll/{scroll_id}"
                    scroll_response = requests.get(scroll_url, headers=headers, timeout=30)
                    
                    print(f"Scroll response status: {scroll_response.status_code}")
                    
                    if scroll_response.status_code != 200:
                        print(f"DSL scroll ended: {scroll_response.status_code} - {scroll_response.text}")
                        break
                    
                    scroll_data = scroll_response.json()
                    scroll_records = scroll_data.get('records', [])
                    scroll_id = scroll_data.get('scroll_id')
                    
                    print(f"Scroll batch {batch_count + 1}: {len(scroll_records)} records, next scroll_id: {'Yes' if scroll_id else 'No'}")
                    
                    if not scroll_records:
                        print("No more records in DSL scroll")
                        break
                    
                    for record in scroll_records:
                        domain = record.get('hostname', '')
                        if domain:
                            if record_type == 'mx':
                                insert_into_sqlite(domain, mx=host, ns=None)
                            else:
                                insert_into_sqlite(domain, mx=None, ns=host)
                            new_records += 1
                    
                    batch_count += 1
                    
                    # Progress update every 10 batches
                    if batch_count % 10 == 0:
                        print(f"Progress: {new_records} records fetched so far...")
            
            elif not scroll_id:
                print("No scroll_id returned - may be all results in first batch")
            else:
                print("Scroll available but no additional records indicated in meta")
            
            flash(f'DSL API Success: Fetched {new_records} records using {endpoint_url}', 'success')
            return
                
        except Exception as e:
            print(f"Error with endpoint {endpoint_url}: {e}")
            continue
    
    # All DSL endpoints failed, fallback to enhanced standard API
    flash('DSL API not available. Using enhanced standard API...', 'warning')
    fetch_reverse_records_enhanced(record_type, host)

def fetch_reverse_records_enhanced(record_type, host):
    """Enhanced version using DSL API with scroll for unlimited results."""
    if not API_KEY:
        flash('SecurityTrails API key not configured', 'error')
        return
    
    headers = {
        'APIKEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    new_records = 0
    
    # Use correct scroll endpoint from official documentation
    scroll_url = f"{API_BASE_URL}/domains/list?include_ips=false&page=1&scroll=true"
    
    # Construct proper query syntax as shown in docs
    if record_type == 'mx':
        query = f"mx = '{host}'"
    else:  # ns
        query = f"ns = '{host}'"
    
    request_body = {
        'query': query
    }
    
    print(f"Enhanced API using official scroll endpoint with query: {query}")
    
    try:
        print(f"Trying official scroll endpoint: {scroll_url}")
        
        time.sleep(0.2)
        response = requests.post(scroll_url, headers=headers, json=request_body, timeout=30)
        
        print(f"Scroll Response status: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f'Scroll API Error: {response.status_code} - {response.text}'
            print(error_msg)
            # Fallback to DSL endpoints if the official scroll fails
            print("Official scroll failed, trying alternative DSL endpoints...")
        else:
            # Success! Process the response
            data = response.json()
            print(f"Scroll Response keys: {list(data.keys())}")
            
            records = data.get('records', [])
            scroll_id = data.get('meta', {}).get('scroll_id')
            meta = data.get('meta', {})
            
            print(f"Official scroll first batch: {len(records)} records")
            print(f"Scroll ID: {scroll_id}")
            print(f"Meta info: {meta}")
            
            # Insert records
            for record in records:
                domain = record.get('hostname', '')
                if domain:
                    if record_type == 'mx':
                        insert_into_sqlite(domain, mx=host, ns=None)
                    else:
                        insert_into_sqlite(domain, mx=None, ns=host)
                    new_records += 1
            
            # Check if there are more results available
            total_records = meta.get('total_records', 0)
            print(f"Total available records according to meta: {total_records}")
            
            # Continue with scroll if available and there are more records
            if scroll_id and total_records > len(records):
                print(f"Starting official scroll to fetch {total_records - len(records)} more records...")
                batch_count = 1
                
                while scroll_id and batch_count < 500:  # Increased limit for large datasets
                    print(f"Official scroll batch {batch_count + 1}...")
                    
                    time.sleep(0.2)
                    
                    scroll_endpoint = f"{API_BASE_URL}/scroll/{scroll_id}"
                    scroll_response = requests.get(scroll_endpoint, headers=headers, timeout=30)
                    
                    print(f"Scroll response status: {scroll_response.status_code}")
                    
                    if scroll_response.status_code != 200:
                        print(f"Official scroll ended: {scroll_response.status_code} - {scroll_response.text}")
                        break
                    
                    scroll_data = scroll_response.json()
                    scroll_records = scroll_data.get('records', [])
                    scroll_id = scroll_data.get('meta', {}).get('scroll_id')
                    
                    print(f"Scroll batch {batch_count + 1}: {len(scroll_records)} records, next scroll_id: {'Yes' if scroll_id else 'No'}")
                    
                    if not scroll_records:
                        print("No more records in official scroll")
                        break
                    
                    for record in scroll_records:
                        domain = record.get('hostname', '')
                        if domain:
                            if record_type == 'mx':
                                insert_into_sqlite(domain, mx=host, ns=None)
                            else:
                                insert_into_sqlite(domain, mx=None, ns=host)
                            new_records += 1
                    
                    batch_count += 1
                    
                    # Progress update every 10 batches
                    if batch_count % 10 == 0:
                        print(f"Enhanced Progress: {new_records} records fetched so far...")
            
            elif not scroll_id:
                print("No scroll_id returned - may be all results in first batch")
            else:
                print("Scroll available but no additional records indicated in meta")
            
            flash(f'Enhanced Official Scroll Success: Fetched {new_records} records', 'success')
            return
                
    except Exception as e:
        print(f"Error with official scroll endpoint: {e}")
    
    # Fallback to alternative DSL endpoints
    print("Trying alternative DSL endpoints...")
    dsl_endpoints = [
        f"{API_BASE_URL}/search/list",         # From documentation examples
        f"{API_BASE_URL}/domains/list-backup"  # From API reference
    ]
    
    # Alternative DSL request body
    alt_request_body = {
        'query': query,
        'scroll': True,
        'include_inactive': False
    }
    
    print(f"Enhanced DSL API with query: {query}")
    
    # Try each endpoint until one works
    for endpoint_url in dsl_endpoints:
        try:
            print(f"Trying DSL endpoint: {endpoint_url}")
            
            time.sleep(0.2)
            response = requests.post(endpoint_url, headers=headers, json=alt_request_body, timeout=30)
            
            print(f"DSL Response status: {response.status_code}")
            
            if response.status_code == 404:
                print(f"Endpoint {endpoint_url} not found, trying next...")
                continue
            elif response.status_code != 200:
                error_msg = f'DSL API Error: {response.status_code} - {response.text}'
                print(error_msg)
                continue
            
            # Success! Process the response
            data = response.json()
            print(f"DSL Response keys: {list(data.keys())}")
            
            records = data.get('records', [])
            scroll_id = data.get('scroll_id')
            meta = data.get('meta', {})
            
            print(f"DSL first batch: {len(records)} records")
            print(f"Scroll ID: {scroll_id}")
            print(f"Meta info: {meta}")
            
            # Insert records
            for record in records:
                domain = record.get('hostname', '')
                if domain:
                    if record_type == 'mx':
                        insert_into_sqlite(domain, mx=host, ns=None)
                    else:
                        insert_into_sqlite(domain, mx=None, ns=host)
                    new_records += 1
            
            # Check if there are more results available
            total_records = meta.get('total_records', 0)
            print(f"Total available records according to meta: {total_records}")
            
            # Continue with scroll if available and there are more records
            if scroll_id and total_records > len(records):
                print(f"Starting scroll to fetch {total_records - len(records)} more records...")
                batch_count = 1
                
                while scroll_id and batch_count < 500:  # Increased limit for large datasets
                    print(f"Enhanced DSL scroll batch {batch_count + 1}...")
                    
                    time.sleep(0.2)
                    
                    scroll_url = f"{API_BASE_URL}/scroll/{scroll_id}"
                    scroll_response = requests.get(scroll_url, headers=headers, timeout=30)
                    
                    print(f"Scroll response status: {scroll_response.status_code}")
                    
                    if scroll_response.status_code != 200:
                        print(f"Enhanced DSL scroll ended: {scroll_response.status_code} - {scroll_response.text}")
                        break
                    
                    scroll_data = scroll_response.json()
                    scroll_records = scroll_data.get('records', [])
                    scroll_id = scroll_data.get('scroll_id')
                    
                    print(f"Scroll batch {batch_count + 1}: {len(scroll_records)} records, next scroll_id: {'Yes' if scroll_id else 'No'}")
                    
                    if not scroll_records:
                        print("No more records in Enhanced DSL scroll")
                        break
                    
                    for record in scroll_records:
                        domain = record.get('hostname', '')
                        if domain:
                            if record_type == 'mx':
                                insert_into_sqlite(domain, mx=host, ns=None)
                            else:
                                insert_into_sqlite(domain, mx=None, ns=host)
                            new_records += 1
                    
                    batch_count += 1
                    
                    # Progress update every 10 batches
                    if batch_count % 10 == 0:
                        print(f"Enhanced Progress: {new_records} records fetched so far...")
            
            elif not scroll_id:
                print("No scroll_id returned - may be all results in first batch")
            else:
                print("Scroll available but no additional records indicated in meta")
            
            flash(f'Enhanced DSL API Success: Fetched {new_records} records using {endpoint_url}', 'success')
            return
                
        except Exception as e:
            print(f"Error with enhanced endpoint {endpoint_url}: {e}")
            continue
    
    # All DSL endpoints failed, fallback to standard API with extended pages
    print("All DSL endpoints failed, falling back to standard API with extended pagination...")
    url = f"{API_BASE_URL}/domains/list"
    
    # Try fetching beyond page 100 to see if the limit is enforced
    for page in range(1, 201):  # Try up to 200 pages
        if record_type == 'mx':
            filter_params = {'mx': host}
        else:
            filter_params = {'ns': host}
        
        request_body = {
            'filter': filter_params,
            'page': page,
            'scroll': False
        }
        
        try:
            time.sleep(0.2)
            response = requests.post(url, headers=headers, json=request_body, timeout=30)
            
            if response.status_code != 200:
                print(f"Standard API fallback stopped at page {page}: {response.status_code}")
                break
            
            data = response.json()
            records = data.get('records', [])
            
            if not records:
                print(f"No more records at page {page}")
                break
            
            # Check if we hit the max_page limit
            meta = data.get('meta', {})
            max_page = meta.get('max_page', 0)
            
            print(f"Standard API fallback page {page}: {len(records)} records, max_page: {max_page}")
            
            for record in records:
                domain = record.get('hostname', '')
                if domain:
                    if record_type == 'mx':
                        insert_into_sqlite(domain, mx=host, ns=None)
                    else:
                        insert_into_sqlite(domain, mx=None, ns=host)
                    new_records += 1
            
            # Respect the API's max_page if set
            if max_page and page >= max_page:
                print(f"Reached API max_page limit: {max_page}")
                break
                
        except Exception as e:
            print(f"Standard API fallback error at page {page}: {e}")
            break
    
    flash(f'Enhanced API (with fallback): Fetched {new_records} records', 'success')

def fetch_reverse_records_bypass_limit(record_type, host):
    """Try various methods to bypass the 100-page limit with better duplicate prevention."""
    if not API_KEY:
        flash('SecurityTrails API key not configured', 'error')
        return
    
    headers = {
        'APIKEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    new_records = 0
    fetched_domains = set()  # Track domains we've already seen
    
    print(f"Starting bypass methods for {record_type.upper()} host: {host}")
    print("IMPORTANT: SecurityTrails has 100-page limits PER KEYWORD COMBINATION")
    print("This means we can get 100 pages for each different filter pattern!")
    
    # Get existing domains to avoid duplicates
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    if record_type == 'mx':
        cursor.execute('SELECT domain FROM domains WHERE mx = ?', (host,))
    else:
        cursor.execute('SELECT domain FROM domains WHERE ns = ?', (host,))
    
    existing_domains = {row[0] for row in cursor.fetchall()}
    conn.close()
    
    print(f"Found {len(existing_domains)} existing domains in database")
    
    # Method 1: Try larger page sizes first (most efficient)
    print("=== Method 1: Larger page sizes (each gets its own 100-page limit) ===")
    for page_size in [500, 1000]:  # Focus on larger sizes
        method_start_count = len(fetched_domains)
        print(f"\\nTrying page size: {page_size} (can get up to {page_size * 100:,} records)")
        
        consecutive_empty = 0
        
        for page in range(1, 101):  # Full 100 pages
            url = f"{API_BASE_URL}/domains/list"
            
            if record_type == 'mx':
                filter_params = {'mx': host}
            else:
                filter_params = {'ns': host}
            
            request_body = {
                'filter': filter_params,
                'page': page,
                'scroll': False,
                'limit': page_size
            }
            
            try:
                time.sleep(0.25)  # Respectful rate limiting
                response = requests.post(url, headers=headers, json=request_body, timeout=30)
                
                if response.status_code != 200:
                    print(f"Page size {page_size}, page {page} failed: {response.status_code}")
                    break
                
                data = response.json()
                records = data.get('records', [])
                
                if not records:
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        print(f"Stopping at page {page} after {consecutive_empty} empty pages")
                        break
                    continue
                
                consecutive_empty = 0
                new_in_page = 0
                
                # Insert only new records
                for record in records:
                    domain = record.get('hostname', '')
                    if domain and domain not in existing_domains and domain not in fetched_domains:
                        fetched_domains.add(domain)
                        if record_type == 'mx':
                            insert_into_sqlite(domain, mx=host, ns=None)
                        else:
                            insert_into_sqlite(domain, mx=None, ns=host)
                        new_records += 1
                        new_in_page += 1
                
                if page % 10 == 0 or new_in_page > 0:  # Progress every 10 pages or when finding new records
                    print(f"Page size {page_size}, page {page}: {len(records)} total, {new_in_page} new unique")
                
                # Check meta info
                meta = data.get('meta', {})
                if meta.get('max_page') and page >= meta.get('max_page'):
                    print(f"Hit max_page limit ({meta.get('max_page')}) with size {page_size}")
                    break
                    
            except Exception as e:
                print(f"Error with page size {page_size}, page {page}: {e}")
                break
        
        method_new = len(fetched_domains) - method_start_count
        print(f"Page size {page_size} result: {method_new:,} new unique domains")
        
        # Don't skip other sizes - each has its own limit!
        if method_new < 1000:  # Only skip if this size didn't work well
            print(f"Page size {page_size} wasn't very effective, trying next size")
    
    print(f"\\n=== Method 1 Summary: {len(fetched_domains):,} total unique domains ===")
    
    # Method 2: Alphabet-based segmentation (each letter gets 100 pages!)
    print("\\n=== Method 2: Alphabet-based segmentation (each pattern gets 100 pages!) ===")
    alphabet_patterns = ['a*', 'b*', 'c*', 'd*', 'e*', 'f*', 'g*', 'h*', 'i*', 'j*', 
                        'k*', 'l*', 'm*', 'n*', 'o*', 'p*', 'q*', 'r*', 's*', 't*', 
                        'u*', 'v*', 'w*', 'x*', 'y*', 'z*', '0*', '1*', '2*', '3*']
    
    print(f"Trying {len(alphabet_patterns)} patterns × 100 pages = up to {len(alphabet_patterns) * 100 * 100:,} more records")
    
    total_patterns_with_results = 0
    
    for i, letter_pattern in enumerate(alphabet_patterns, 1):
        method_start_count = len(fetched_domains)
        pattern_records = 0
        
        consecutive_empty = 0
        
        for page in range(1, 101):  # Full 100 pages per pattern
            url = f"{API_BASE_URL}/domains/list"
            
            if record_type == 'mx':
                filter_params = {
                    'mx': host,
                    'hostname': letter_pattern
                }
            else:
                filter_params = {
                    'ns': host,
                    'hostname': letter_pattern
                }
            
            request_body = {
                'filter': filter_params,
                'page': page,
                'scroll': False
            }
            
            try:
                time.sleep(0.2)
                response = requests.post(url, headers=headers, json=request_body, timeout=30)
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                records = data.get('records', [])
                
                if not records:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:  # Stop earlier for alphabet patterns
                        break
                    continue
                
                consecutive_empty = 0
                new_in_page = 0
                
                # Insert only new records
                for record in records:
                    domain = record.get('hostname', '')
                    if domain and domain not in existing_domains and domain not in fetched_domains:
                        fetched_domains.add(domain)
                        if record_type == 'mx':
                            insert_into_sqlite(domain, mx=host, ns=None)
                        else:
                            insert_into_sqlite(domain, mx=None, ns=host)
                        new_records += 1
                        new_in_page += 1
                        pattern_records += 1
                
                # Check meta info
                meta = data.get('meta', {})
                if meta.get('max_page') and page >= meta.get('max_page'):
                    break
                    
            except Exception as e:
                print(f"Error with letter '{letter_pattern}', page {page}: {e}")
                break
        
        method_new = len(fetched_domains) - method_start_count
        if method_new > 0:
            total_patterns_with_results += 1
            print(f"Pattern '{letter_pattern}' ({i}/{len(alphabet_patterns)}): {method_new:,} new unique domains")
        
        # Stop if we've collected a huge amount
        if len(fetched_domains) > 500000:
            print(f"Reached {len(fetched_domains):,} domains, stopping alphabet method")
            break
    
    print(f"\\nAlphabet method: {total_patterns_with_results}/{len(alphabet_patterns)} patterns had results")
    
    print(f"=== Final Summary ===")
    print(f"Total unique domains fetched: {len(fetched_domains)}")
    print(f"New records added to database: {new_records}")
    
    flash(f'Bypass methods fetched {new_records} NEW unique records (avoided {len(fetched_domains) - new_records} duplicates)', 'success')

def fetch_reverse_records(record_type, host):
    """Original standard API method."""
    if not API_KEY:
        flash('SecurityTrails API key not configured', 'error')
        return
    
    headers = {
        'APIKEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    page = 1
    new_records = 0
    
    while True:
        # Use the correct SecurityTrails API endpoint
        url = f"{API_BASE_URL}/domains/list"
        
        # Construct filter based on record type
        if record_type == 'mx':
            filter_params = {'mx': host}
        else:  # ns
            filter_params = {'ns': host}
        
        request_body = {
            'filter': filter_params,
            'page': page,
            'scroll': False
        }
        
        try:
            # Rate limiting: 5 requests per second = 0.2 seconds between requests
            time.sleep(0.2)
            
            response = requests.post(url, headers=headers, json=request_body, timeout=30)
            
            if response.status_code != 200:
                error_msg = f'API Error: {response.status_code} - {response.text}'
                flash(error_msg, 'error')
                break
            
            data = response.json()
            records = data.get('records', [])
            
            if not records:
                break
            
            # Insert records into SQLite
            for record in records:
                domain = record.get('hostname', '')
                if domain:
                    if record_type == 'mx':
                        insert_into_sqlite(domain, mx=host, ns=None)
                    else:  # ns
                        insert_into_sqlite(domain, mx=None, ns=host)
                    new_records += 1
            
            page += 1
            
            # Check if we've reached the end - SecurityTrails typically returns fewer results on last page
            # Also check for meta information about pagination
            meta = data.get('meta', {})
            if len(records) == 0 or (meta.get('max_page') and page > meta.get('max_page')):
                break
                
        except requests.RequestException as e:
            flash(f'Network error: {str(e)}', 'error')
            break
        except Exception as e:
            flash(f'Error fetching data: {str(e)}', 'error')
            break
    
    flash(f'Fetched {new_records} new records for {record_type.upper()} host: {host}', 'success')
    """Fetch reverse records from SecurityTrails API with pagination."""
    if not API_KEY:
        flash('SecurityTrails API key not configured', 'error')
        return
    
    headers = {
        'APIKEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    page = 1
    new_records = 0
    
    while True:
        # Use the correct SecurityTrails API endpoint
        url = f"{API_BASE_URL}/domains/list"
        
        # Construct filter based on record type
        if record_type == 'mx':
            filter_params = {'mx': host}
        else:  # ns
            filter_params = {'ns': host}
        
        request_body = {
            'filter': filter_params,
            'page': page,
            'scroll': False
        }
        
        try:
            # Rate limiting: 5 requests per second = 0.2 seconds between requests
            time.sleep(0.2)
            
            response = requests.post(url, headers=headers, json=request_body, timeout=30)
            
            if response.status_code != 200:
                error_msg = f'API Error: {response.status_code} - {response.text}'
                flash(error_msg, 'error')
                break
            
            data = response.json()
            records = data.get('records', [])
            
            if not records:
                break
            
            # Insert records into SQLite
            for record in records:
                domain = record.get('hostname', '')
                if domain:
                    if record_type == 'mx':
                        insert_into_sqlite(domain, mx=host, ns=None)
                    else:  # ns
                        insert_into_sqlite(domain, mx=None, ns=host)
                    new_records += 1
            
            page += 1
            
            # Check if we've reached the end - SecurityTrails typically returns fewer results on last page
            # Also check for meta information about pagination
            meta = data.get('meta', {})
            if len(records) == 0 or (meta.get('max_page') and page > meta.get('max_page')):
                break
                
        except requests.RequestException as e:
            flash(f'Network error: {str(e)}', 'error')
            break
        except Exception as e:
            flash(f'Error fetching data: {str(e)}', 'error')
            break
    
    flash(f'Fetched {new_records} new records for {record_type.upper()} host: {host}', 'success')

@app.route('/')
def home():
    """Home page with search form."""
    return render_template('search.html')

@app.route('/results', methods=['GET', 'POST'])
def results():
    """Display search results with pagination."""
    if request.method == 'POST':
        record_type = request.form.get('type')
        host = request.form.get('host')
        refresh = request.form.get('refresh') == 'on'
        use_scroll = request.form.get('use_scroll') == 'on'
    else:
        record_type = request.args.get('type')
        host = request.args.get('host')
        refresh = request.args.get('refresh') == 'true'
        use_scroll = request.args.get('use_scroll') == 'true'
    
    page = int(request.args.get('page', 1))
    
    if not record_type or not host:
        flash('Please provide both record type and host', 'error')
        return redirect(url_for('home'))
    
    # Test API connection first
    api_success, api_message = test_api_connection()
    if not api_success:
        flash(f'API Connection Failed: {api_message}', 'error')
        return redirect(url_for('home'))
    
    # Check cache and fetch if needed
    if not check_cache(record_type, host) or refresh:
        if use_scroll:
            flash('Fetching unlimited data using DSL + Scroll API...', 'info')
            fetch_reverse_records_with_scroll(record_type, host)
        else:
            bypass_limit = request.form.get('bypass_limit') == 'on' or request.args.get('bypass_limit') == 'true'
            if bypass_limit:
                flash('Trying bypass methods to get more than 10,000 results...', 'info')
                fetch_reverse_records_bypass_limit(record_type, host)
            else:
                flash('Fetching data from SecurityTrails API (up to 10,000 results)...', 'info')
                fetch_reverse_records(record_type, host)
    
    # Get paginated results
    records, total_count = query_sqlite(record_type, host, page)
    
    # Calculate pagination info
    per_page = 50
    total_pages = (total_count + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    return render_template('results.html', 
                         records=records,
                         record_type=record_type,
                         host=host,
                         page=page,
                         total_pages=total_pages,
                         total_count=total_count,
                         has_prev=has_prev,
                         has_next=has_next)

@app.route('/test-api')
def test_api():
    """Test API endpoint for debugging."""
    success, message = test_api_connection()
    if success:
        flash(f'✅ {message}', 'success')
    else:
        flash(f'❌ {message}', 'error')
    return redirect(url_for('home'))

@app.route('/export/<record_type>/<host>')
def export_csv(record_type, host):
    """Export all results to CSV."""
    records = query_all_sqlite(record_type, host)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Domain', 'MX', 'NS', 'Fetched At'])
    
    # Write data
    for record in records:
        writer.writerow(record)
    
    # Prepare file for download
    output.seek(0)
    
    # Create BytesIO for Flask send_file
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    filename = f"{record_type}_{host}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return send_file(
        mem,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
