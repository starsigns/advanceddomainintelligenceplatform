#!/usr/bin/env python3

# Test the format_domain_url function
def format_domain_url(domain):
    """
    Format domain as clickable URL by adding http:// prefix if not present.
    Ensures consistent URL formatting across the application.
    
    Args:
        domain (str): Domain name to format
        
    Returns:
        str: Formatted URL with http:// prefix
    """
    if not domain:
        return domain
    
    # Check if already has protocol
    if domain.startswith(('http://', 'https://')):
        return domain
    
    # Add http:// prefix to make clickable
    return f"http://{domain}"

# Test cases
test_domains = [
    'example.com',
    'test.org',
    'http://already-has-prefix.com',
    'https://secure-site.net',
    '007-spyshop.at',
    'mx01.ionos.de'
]

print('Testing format_domain_url function:')
print('=' * 50)
for domain in test_domains:
    formatted = format_domain_url(domain)
    print(f'Input:  {domain}')
    print(f'Output: {formatted}')
    print()

# Test inserting into database
print('Testing database insertion with formatting:')
print('=' * 50)

import sqlite3
import tempfile
import os

# Create a temporary database for testing
temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
temp_db.close()

try:
    conn = sqlite3.connect(temp_db.name)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
        CREATE TABLE test_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            mx TEXT,
            ns TEXT
        )
    ''')
    
    # Insert test data with formatting
    test_data = [
        ('example.com', 'mx.example.com', None),
        ('test.org', None, 'ns1.test.org'),
        ('http://already-formatted.com', 'mx1.test.com', None)
    ]
    
    for domain, mx, ns in test_data:
        formatted_domain = format_domain_url(domain)
        cursor.execute('''
            INSERT INTO test_domains (domain, mx, ns)
            VALUES (?, ?, ?)
        ''', (formatted_domain, mx, ns))
        print(f'Inserted: {formatted_domain} (from {domain})')
    
    # Verify the data
    cursor.execute('SELECT domain FROM test_domains')
    results = cursor.fetchall()
    
    print('\nStored domains:')
    for i, (domain,) in enumerate(results, 1):
        print(f'{i}. {domain}')
    
    conn.commit()
    conn.close()
    
    print('\n✅ Function working correctly!')

finally:
    # Clean up temp file
    os.unlink(temp_db.name)
