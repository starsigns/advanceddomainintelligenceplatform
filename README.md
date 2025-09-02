# Advanced Domain Intelligence Platform

A comprehensive Flask web application for advanced domain intelligence operations, featuring reverse MX and NS lookups with support for multiple DNS providers including ViewDNS and SecurityTrails. Find all domains that use specific mail servers or name servers with enterprise-grade caching, export capabilities, and unlimited data harvesting.

## Features

- 🔍 **Reverse MX Lookup**: Find all domains using a specific mail server
- 🌐 **Reverse NS Lookup**: Find all domains using a specific name server  
- � **Multiple Providers**: Support for ViewDNS (unlimited) and SecurityTrails APIs
- �💾 **SQLite Caching**: Results cached locally with deduplication and session tracking
- 📄 **Advanced Pagination**: Browse millions of results with efficient pagination
- 📊 **Multi-Format Export**: Export to CSV, Excel (.xlsx), and chunked archives
- 📈 **Background Harvesting**: Automated data collection with progress tracking
- ⚡ **Smart Rate Limiting**: Respects API limits with automatic retry logic
- 🔄 **Incremental Updates**: Only fetches new data, preserves existing cache
- 📋 **Real-time Statistics**: Live dashboard with collection progress and stats
- 🎯 **Enterprise Scale**: Handle millions of domains with multi-sheet Excel export

## Setup

### 1. Clone Repository
```bash
git clone https://github.com/starsigns/advanceddomainintelligenceplatform.git
cd advanceddomainintelligenceplatform
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
2. Get your API key from [ViewDNS](https://viewdns.info/api/pricing/) (recommended) or [SecurityTrails](https://securitytrails.com/app/account/credentials)
3. Update `.env` with your API configuration:
```
# Primary provider (recommended for unlimited access)
VIEWDNS_API_KEY=your_viewdns_api_key_here
DNS_PROVIDER=viewdns

# Alternative provider (limited to 50 pages)
SECURITYTRAILS_API_KEY=your_securitytrails_api_key_here
# DNS_PROVIDER=securitytrails

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
2. Enter a mail server hostname (e.g., `mx01.ionos.de`, `aspmx.l.google.com`)
3. Click "Start Collection" to begin automated harvesting of all domains using that mail server
4. Monitor real-time progress and statistics on the dashboard

### NS Record Lookup
1. Select "NS (Name Server)" from the dropdown  
2. Enter a name server hostname (e.g., `ns1.google.com`, `dns1.registrar-servers.com`)
3. Click "Start Collection" to begin automated harvesting of all domains using that name server
4. Track collection progress with live updates

### Advanced Features
- **Background Harvesting**: Automated collection runs in background threads
- **Real-time Dashboard**: Live statistics and progress tracking
- **Smart Caching**: Results automatically cached with deduplication
- **Multiple Export Formats**: 
  - CSV (standard and chunked for large datasets)
  - Excel (.xlsx with multi-sheet support for millions of records)
  - ZIP archives for very large datasets
- **Intelligent Pagination**: Handles millions of records efficiently
- **Provider Switching**: ViewDNS for unlimited access, SecurityTrails as backup
- **Session Tracking**: Each collection session is tracked separately

## Database Schema

The application uses SQLite with an enhanced schema for enterprise-scale operations:

```sql
CREATE TABLE domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    mx TEXT,
    ns TEXT, 
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    provider TEXT DEFAULT 'viewdns',
    session_id TEXT,
    UNIQUE(domain, mx, ns)
);

CREATE INDEX idx_mx ON domains(mx);
CREATE INDEX idx_ns ON domains(ns);
CREATE INDEX idx_provider ON domains(provider);
CREATE INDEX idx_session ON domains(session_id);
CREATE INDEX idx_fetched_at ON domains(fetched_at);
```

### Key Enhancements:
- **Provider Tracking**: Track which API provider supplied each record
- **Session Management**: Group records by collection session
- **Performance Indexing**: Optimized for large-scale data operations
- **Deduplication**: Automatic duplicate prevention across providers

## API Providers & Rate Limiting

### ViewDNS API (Recommended)
- **Unlimited pagination**: No artificial limits on data collection
- **Rate limiting**: Automatic throttling with retry logic
- **Timeout handling**: 30-second timeout with graceful error recovery
- **Cost-effective**: Pay-per-query pricing for large-scale operations

### SecurityTrails API (Backup)
- **Page limit**: Limited to 50 pages per query (≈50,000 records)
- **Rate limiting**: 5 requests per second with 0.2s delay
- **Fallback option**: Used when ViewDNS is unavailable

### Smart Provider Selection
- Primary: ViewDNS for unlimited data access
- Fallback: SecurityTrails for smaller datasets
- Automatic switching based on availability and requirements

## File Structure

```
advanceddomainintelligenceplatform/
├── app.py              # Main Flask application with multi-provider support
├── requirements.txt    # Python dependencies (Flask, openpyxl, xlsxwriter, etc.)
├── .env.example       # Environment variables template
├── .env               # Your actual environment variables (not in git)
├── domains.db         # SQLite database (created automatically)
├── templates/
│   ├── base.html      # Enhanced base template with Bootstrap 5
│   ├── index.html     # Modern dashboard with real-time stats
│   └── results.html   # Advanced results view with export options
├── static/            # Static assets (auto-created)
├── venv/              # Virtual environment (auto-created)
└── README.md          # This documentation
```

## Development

To run in development mode with full debugging:
```bash
# Set environment variables
export FLASK_ENV=development  # Linux/Mac
set FLASK_ENV=development     # Windows CMD
$env:FLASK_ENV="development"  # Windows PowerShell

# Run with virtual environment
.\venv\Scripts\python.exe app.py  # Windows
./venv/bin/python app.py          # Linux/Mac
```

### Development Features
- **Auto-reload**: Flask automatically reloads on code changes
- **Debug mode**: Detailed error pages and debugging tools
- **Real-time logging**: Comprehensive logging for API calls and operations
- **Performance monitoring**: Track harvesting speed and API performance

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

## Advanced Export Capabilities

### Multi-Format Export Support
- **CSV Export**: Standard comma-separated values
- **Excel Export**: Professional .xlsx files with multiple worksheets
- **Chunked Archives**: ZIP files for very large datasets
- **Smart File Naming**: Automatic timestamped filenames

### Excel Multi-Sheet Export
For large datasets exceeding Excel's 1M row limit per sheet:
- **Sheet 1**: Rows 1-1,048,576
- **Sheet 2**: Rows 1,048,577-2,097,152  
- **Sheet 3**: And so on...
- **Single File**: All data in one convenient Excel file

### Export Features
- **Progress Tracking**: Real-time export progress
- **Memory Efficient**: Handles millions of records without memory issues
- **Format Detection**: Automatic format selection based on dataset size
- **Error Handling**: Graceful handling of export errors

## Performance & Scalability

### Proven Scale
- ✅ **2.9M+ domains**: Successfully tested with 2.94 million domain records
- ⚡ **Background Processing**: Non-blocking harvesting operations
- 💾 **Memory Efficient**: Optimized for large dataset operations
- 🔄 **Resume Capability**: Continue interrupted harvesting sessions

### Technical Specifications
- **Database**: SQLite with performance indexing
- **Threading**: Background harvesting with progress tracking
- **Memory Usage**: Optimized for large dataset processing
- **Export Speed**: Efficient multi-format export generation

## API Providers

### ViewDNS API (Primary)
This application primarily uses ViewDNS for unlimited domain intelligence. Visit [ViewDNS](https://viewdns.info/api/pricing/) to:
- Sign up for an API account
- Choose a suitable pricing plan
- Get your API key from the dashboard
- Review API documentation and capabilities

### SecurityTrails API (Backup)
Fallback support for SecurityTrails API. Visit [SecurityTrails](https://securitytrails.com/) to:
- Sign up for an account
- Get your API key from the credentials page
- Review API documentation and limits

### Recommended Setup
1. **Primary**: ViewDNS API for unlimited data collection
2. **Backup**: SecurityTrails API for redundancy
3. **Configuration**: Set `DNS_PROVIDER=viewdns` in your `.env` file
