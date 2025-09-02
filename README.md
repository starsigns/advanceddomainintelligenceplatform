# SecurityTrails Reverse MX/NS Fetcher

A Flask web application for performing reverse MX and NS lookups using the SecurityTrails API. Find all domains that use specific mail servers or name servers.

## Features

- 🔍 **Reverse MX Lookup**: Find all domains using a specific mail server
- 🌐 **Reverse NS Lookup**: Find all domains using a specific name server  
- 💾 **SQLite Caching**: Results cached locally to avoid repeated API calls
- 📄 **Pagination**: Browse results with easy pagination
- 📊 **CSV Export**: Export all results to CSV for analysis
- ⚡ **Rate Limiting**: Respects SecurityTrails API limits (5 req/sec)
- 🔄 **Incremental Updates**: Only fetches new data, preserves existing cache

## Setup

### 1. Clone Repository
```bash
git clone https://github.com/starsigns/securitytrailsfetcher.git
cd securitytrailsfetcher
```

### 2. Create Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# or
source venv/bin/activate     # Linux/Mac
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Key
1. Copy `.env.example` to `.env`
2. Get your API key from [SecurityTrails](https://securitytrails.com/app/account/credentials)
3. Update `.env` with your API key:
```
SECURITYTRAILS_API_KEY=your_actual_api_key_here
SECRET_KEY=your-secret-key-for-flask-sessions
```

### 5. Run Application
```bash
python app.py
```

The application will be available at: http://localhost:5000

## Usage

### MX Record Lookup
1. Select "MX (Mail Exchange)" from the dropdown
2. Enter a mail server hostname (e.g., `mail.google.com`)
3. Click Search to find all domains using that mail server

### NS Record Lookup
1. Select "NS (Name Server)" from the dropdown  
2. Enter a name server hostname (e.g., `ns1.google.com`)
3. Click Search to find all domains using that name server

### Features
- **Caching**: Results are automatically cached in SQLite
- **Refresh**: Check "Force refresh" to get latest data from API
- **Pagination**: Browse through results 50 at a time
- **Export**: Download all results as CSV file
- **Rate Limiting**: Automatically handles API rate limits

## Database Schema

The application uses SQLite with the following schema:

```sql
CREATE TABLE domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    mx TEXT,
    ns TEXT, 
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, mx, ns)
);

CREATE INDEX idx_mx ON domains(mx);
CREATE INDEX idx_ns ON domains(ns);
```

## API Rate Limiting

The application respects SecurityTrails API limits:
- Maximum 5 requests per second
- Automatic 0.2 second delay between requests
- Handles pagination automatically
- Graceful error handling for API failures

## File Structure

```
securitytrailsfetcher/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
├── .env               # Your actual environment variables (not in git)
├── domains.db         # SQLite database (created automatically)
├── templates/
│   ├── base.html      # Base template
│   ├── search.html    # Search form
│   └── results.html   # Results display
└── README.md          # This file
```

## Development

To run in development mode:
```bash
export FLASK_ENV=development  # Linux/Mac
set FLASK_ENV=development     # Windows CMD
$env:FLASK_ENV="development"  # Windows PowerShell
python app.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please check the LICENSE file for details.

## Support

For issues or questions:
1. Check the existing issues on GitHub
2. Create a new issue with detailed information
3. Include error messages and steps to reproduce

## SecurityTrails API

This application requires a SecurityTrails API key. Visit [SecurityTrails](https://securitytrails.com/) to:
- Sign up for an account
- Get your API key from the credentials page
- Review API documentation and limits
