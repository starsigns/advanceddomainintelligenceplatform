import sqlite3

conn = sqlite3.connect('domains.db')
cursor = conn.cursor()

# Check the latest domains to see if they have http:// prefix
cursor.execute('SELECT domain FROM domains ORDER BY id DESC LIMIT 10')
recent_domains = cursor.fetchall()

print('Recent domains (checking for http:// prefix):')
for i, domain in enumerate(recent_domains, 1):
    print(f'{i}. {domain[0]}')

# Check if any domains have http:// prefix
cursor.execute("SELECT COUNT(*) FROM domains WHERE domain LIKE 'http://%'")
http_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM domains')
total_count = cursor.fetchone()[0]

print(f'\nDomains with http:// prefix: {http_count:,}')
print(f'Total domains: {total_count:,}')
print(f'Percentage with http://: {(http_count/total_count*100):.1f}%')

# Check the new ns1.world4you.at data
cursor.execute('SELECT COUNT(*) FROM domains WHERE ns = "ns1.world4you.at"')
ns_count = cursor.fetchone()[0]
print(f'\nDomains for ns1.world4you.at: {ns_count:,}')

if ns_count > 0:
    cursor.execute('SELECT domain FROM domains WHERE ns = "ns1.world4you.at" LIMIT 5')
    sample = cursor.fetchall()
    print('Sample ns1.world4you.at domains:')
    for i, domain in enumerate(sample, 1):
        print(f'  {i}. {domain[0]}')

# Also check for a sample of existing domains
cursor.execute("SELECT domain FROM domains WHERE domain LIKE 'http://%' LIMIT 5")
sample_http = cursor.fetchall()

if sample_http:
    print('\nSample domains with http:// prefix:')
    for i, domain in enumerate(sample_http, 1):
        print(f'{i}. {domain[0]}')
else:
    print('\nNo domains found with http:// prefix yet.')

conn.close()
