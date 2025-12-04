# OKTA IGA BACKUP SYSTEM - ASYNC & MODULAR

A comprehensive, production-ready backup system for Okta Identity Governance and Administration (IGA) APIs with async processing and modular architecture.

## 🎯 CURRENT STATUS: REFACTORED & ENHANCED

- **ARCHITECTURE**: Fully refactored modular design ✅
- **PERFORMANCE**: Async processing with concurrency control ✅
- **CONFIGURATION**: Dynamic endpoint control via JSON ✅
- **MODULARITY**: Clean separation of concerns ✅

## 📁 PROJECT STRUCTURE

```
OKTA_IGA/
├── configs/                         # 📋 All JSON configuration files
│   ├── config.json                  # System configuration (environments)
│   ├── endpoints.json               # Full backup configuration (all endpoints)
│   ├── endpoints_minimal.json      # Minimal backup (campaigns + reviews only)
│   └── endpoints_test.json          # Test scenario configuration
├── okta_iga/                        # 🔥 Main package (fully modular)
│   ├── __init__.py                  # Package entry point
│   ├── backup_system.py             # Main backup orchestrator
│   ├── config/                      # ⚙️ Configuration management
│   │   ├── __init__.py
│   │   ├── config_loader.py         # System config loader (environments, DB)
│   │   └── endpoint_config.py      # Dynamic endpoint control loader
│   ├── endpoints/                   # 📋 API endpoint definitions
│   │   ├── global_endpoints.py      # Global endpoint configs
│   │   └── resource_endpoints.py    # Resource-specific configs
│   ├── auth/                        # 🔐 Authentication module
│   │   └── authentication.py       # OAuth & SSWS token handling
│   ├── crypto/                      # (removed) Encryption utilities
│   └── database/                    # (removed) Database connections
├── run_backup.py                    # 🚀 Main backup runner
└── envs/                           # Environment configurations (.env files)
```

## 🚀 QUICK START

### Prerequisites
- Python 3.7+
- Okta domain with IGA features enabled
- Credentials configured in `configs/credentials.json` or environment files

### Basic Usage

#### Full Backup (All endpoints)
```bash
python run_backup.py
```

#### Test Mode (1 object per endpoint)
```bash
# Edit run_backup.py and set test_mode = True
python run_backup.py
```

#### Custom Endpoint Selection
```bash
# Edit configs/endpoints.json to enable/disable endpoints
# Then run normal backup
python run_backup.py
```

## ⚙️ DYNAMIC ENDPOINT CONFIGURATION

Control which endpoints run without code changes using JSON configuration:

### Configuration File Structure
```json
{
  "global_endpoints": {
    "campaigns": {"enabled": true},
    "reviews": {"enabled": true},
    "request_types": {"enabled": false},
    "requests_v1": {"enabled": true}
  },
  "resource_endpoints": {
    "grants": {"enabled": true},
    "entitlements": {"enabled": false},
    "request_conditions": {"enabled": true}
  }
}
```

### Predefined Configuration Files
- **`configs/endpoints.json`** - Full backup (all endpoints enabled)
- **`configs/endpoints_minimal.json`** - Minimal backup (campaigns + reviews only)
- **`configs/endpoints_test.json`** - Custom test configuration
- **`configs/config.json`** - System configuration (environments, database, SSH)

### Logic
- `"enabled": true` → Endpoint will run
- `"enabled": false` or missing → Endpoint skipped

## 🏗️ MODULAR ARCHITECTURE

### Core Modules

#### 📋 Endpoints (`okta_iga/endpoints/`)
- **Global Endpoints**: Campaign, reviews, requests, etc.
- **Resource Endpoints**: Resource-specific endpoints requiring resourceId
- Clean separation of API definitions from business logic

#### 🔐 Authentication (`okta_iga/auth/`)
- **SSWS API Token** support
- **OAuth 2.0** client credentials flow
- Automatic token refresh and validation
- Unified authentication interface

#### Notes
- Database-backed credential and Blowfish encryption support has been removed. Store credentials in `configs/credentials.json` or environment variables.

#### ⚙️ Configuration (`okta_iga/config/`)
- **System Configuration**: `config_loader.py` handles environments, database, SSH
- **Endpoint Configuration**: `endpoint_config.py` handles dynamic endpoint control
- **JSON-based control**: Runtime enable/disable of endpoints via JSON files
- **Multiple scenarios**: Support for different backup configurations
- **Validation and error handling** for all configurations

## ✅ SUPPORTED ENDPOINTS

### Global Endpoints (Step 1)
- **campaigns** - IGA access review campaigns
- **reviews** - Access review instances
- **request_types** - Available request types
- **requests_v1** - Access requests (v1 API)
- **requests_v2** - Access requests (v2 API)
- **request_settings_global** - Global request settings
- **entitlement_bundles** - Grouped entitlements
- **collections** - Resource collections
- **risk_rules** - Risk assessment rules
- **delegates** - Delegation settings

### Resource Endpoints (Step 2)
- **grants** - Access grants per resource
- **entitlements** - Entitlements per resource
- **request_conditions** - Conditional access rules
- **request_settings** - Resource-specific settings
- **request_sequences** - Multi-step workflows
- **principal_entitlements** - User entitlements per resource
- **principal_access** - User access per resource

## 🔧 KEY FEATURES

### Async Processing
- ✅ **Concurrent endpoint processing** with semaphore controls
- ✅ **Parallel object fetching** for details
- ✅ **Smart rate limiting** with burst handling
- ✅ **Progress monitoring** with real-time updates

### Dynamic Control
- ✅ **JSON-based endpoint configuration**
- ✅ **Runtime enable/disable** without code changes
- ✅ **Multiple backup scenarios** (full/minimal/custom)
- ✅ **Flexible configuration management**

### Production Features
- ✅ **Environment management** (dev/staging/prod)
- ✅ **Comprehensive error handling** and logging
- ✅ **Resource-aware processing** for dependent endpoints

### Data Management
- ✅ **Individual object files** with metadata
- ✅ **List files** for bulk operations
- ✅ **Detailed object files** from detail endpoints
- ✅ **Consistent JSON structure** across all endpoints

## 📊 BACKUP OUTPUT STRUCTURE

```
backup/environment/tenant_X_customer_Y/backup_YYYYMMDD_HHMMSS/
├── backup_summary.json              # Overall backup metadata
├── campaigns/                       # Global endpoint data
│   ├── list.json                   # All campaigns from list endpoint
│   ├── list_detailed.json          # All campaigns with detail data
│   ├── campaign1.json              # Individual campaign file
│   └── campaign2.json
├── reviews/                         # Global endpoint data
│   └── ...
├── resources/                       # Resource-specific data
│   ├── resourceId1/
│   │   ├── grants/
│   │   ├── entitlements/
│   │   └── request_conditions/
│   └── resourceId2/
│       └── ...
└── ...
```

## 🚀 PERFORMANCE & SCALABILITY

### Concurrency Controls
- **API calls**: 15 concurrent requests max
- **Endpoints**: 3 concurrent endpoints max
- **Detail calls**: 10 concurrent per endpoint
- **Resource discovery**: 8 concurrent resources

### Rate Limiting
- **Rate limit**: 50 requests/minute (configurable)
- **Burst size**: 10 requests (configurable)
- **Adaptive throttling** for 429 responses
- **Exponential backoff** for failures
