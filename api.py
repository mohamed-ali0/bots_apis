#!/usr/bin/env python3
"""
E-Modal Authentication API
=========================

Professional Flask API for E-Modal login automation using:
- Modular reCAPTCHA handler with fallbacks
- Comprehensive error handling and reporting
- VPN integration support
- Session token extraction
- Production-ready logging

Usage:
    python api.py

Endpoints:
    POST /login - Authenticate with E-Modal
    GET /health - Health check
"""

from flask import Flask, request, jsonify
import logging
import os
from datetime import datetime

from emodal_login_handler import emodal_login, LoginErrorType


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('emodal_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "E-Modal Authentication API",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


@app.route('/login', methods=['POST'])
def login():
    """
    E-Modal login endpoint
    
    Expected JSON payload:
    {
        "username": "your_username",
        "password": "your_password",
        "captcha_api_key": "your_2captcha_api_key",
        "use_vpn": true  // optional, defaults to true
    }
    
    Returns:
    {
        "success": true/false,
        "error_type": null or error type,
        "error_message": null or error description,
        "final_url": final URL after login,
        "page_title": final page title,
        "session_tokens": extracted authentication tokens,
        "cookies": browser cookies,
        "recaptcha_method": method used for reCAPTCHA,
        "timestamp": request timestamp,
        "request_id": unique request identifier
    }
    """
    
    request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    timestamp = datetime.now().isoformat()
    
    logger.info(f"[{request_id}] Login request received")
    
    try:
        # Validate request
        if not request.is_json:
            logger.error(f"[{request_id}] Invalid request - not JSON")
            return jsonify({
                "success": False,
                "error_type": "invalid_request",
                "error_message": "Request must be JSON",
                "request_id": request_id,
                "timestamp": timestamp
            }), 400
        
        data = request.get_json()
        
        # Required fields
        username = data.get('username')
        password = data.get('password')
        captcha_api_key = data.get('captcha_api_key')
        
        if not all([username, password, captcha_api_key]):
            missing_fields = []
            if not username:
                missing_fields.append('username')
            if not password:
                missing_fields.append('password')
            if not captcha_api_key:
                missing_fields.append('captcha_api_key')
            
            logger.error(f"[{request_id}] Missing required fields: {missing_fields}")
            return jsonify({
                "success": False,
                "error_type": "missing_fields",
                "error_message": f"Missing required fields: {', '.join(missing_fields)}",
                "required_fields": ["username", "password", "captcha_api_key"],
                "request_id": request_id,
                "timestamp": timestamp
            }), 400
        
        # Optional fields
        use_vpn = data.get('use_vpn', True)
        
        logger.info(f"[{request_id}] Starting login for user: {username}")
        logger.info(f"[{request_id}] VPN profile: {'enabled' if use_vpn else 'disabled'}")
        
        # Perform login
        try:
            result = emodal_login(
                username=username,
                password=password,
                captcha_api_key=captcha_api_key,
                use_vpn=use_vpn
            )
            
            # Add request metadata
            result.update({
                "request_id": request_id,
                "timestamp": timestamp
            })
            
            # Log result
            if result.get('success'):
                logger.info(f"[{request_id}] Login successful for user: {username}")
                logger.info(f"[{request_id}] Final URL: {result.get('final_url', 'N/A')}")
                logger.info(f"[{request_id}] reCAPTCHA method: {result.get('recaptcha_method', 'N/A')}")
                logger.info(f"[{request_id}] Session tokens: {len(result.get('session_tokens', {}))} extracted")
            else:
                logger.warning(f"[{request_id}] Login failed for user: {username}")
                logger.warning(f"[{request_id}] Error type: {result.get('error_type', 'unknown')}")
                logger.warning(f"[{request_id}] Error message: {result.get('error_message', 'N/A')}")
            
            # Return appropriate HTTP status
            status_code = 200 if result.get('success') else 401
            
            # For security, don't include sensitive cookie values in logs
            if result.get('cookies'):
                result['cookie_count'] = len(result['cookies'])
            
            return jsonify(result), status_code
            
        except Exception as login_error:
            logger.error(f"[{request_id}] Login process error: {str(login_error)}")
            return jsonify({
                "success": False,
                "error_type": "login_process_error",
                "error_message": f"Login process failed: {str(login_error)}",
                "request_id": request_id,
                "timestamp": timestamp
            }), 500
    
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected API error: {str(e)}")
        return jsonify({
            "success": False,
            "error_type": "api_error", 
            "error_message": f"Unexpected API error: {str(e)}",
            "request_id": request_id,
            "timestamp": timestamp
        }), 500


@app.route('/login/batch', methods=['POST'])
def batch_login():
    """
    Batch login endpoint for multiple credentials
    
    Expected JSON payload:
    {
        "credentials": [
            {
                "username": "user1",
                "password": "pass1"
            },
            {
                "username": "user2", 
                "password": "pass2"
            }
        ],
        "captcha_api_key": "your_2captcha_api_key",
        "use_vpn": true
    }
    
    Returns array of login results
    """
    
    request_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    timestamp = datetime.now().isoformat()
    
    logger.info(f"[{request_id}] Batch login request received")
    
    try:
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Request must be JSON",
                "request_id": request_id
            }), 400
        
        data = request.get_json()
        credentials = data.get('credentials', [])
        captcha_api_key = data.get('captcha_api_key')
        use_vpn = data.get('use_vpn', True)
        
        if not captcha_api_key:
            return jsonify({
                "success": False,
                "error": "captcha_api_key required",
                "request_id": request_id
            }), 400
        
        if not credentials or len(credentials) == 0:
            return jsonify({
                "success": False,
                "error": "No credentials provided",
                "request_id": request_id
            }), 400
        
        logger.info(f"[{request_id}] Processing {len(credentials)} credential pairs")
        
        results = []
        
        for i, cred in enumerate(credentials):
            username = cred.get('username')
            password = cred.get('password')
            
            if not username or not password:
                results.append({
                    "success": False,
                    "error_type": "invalid_credentials",
                    "error_message": f"Credential pair {i+1}: missing username or password"
                })
                continue
            
            logger.info(f"[{request_id}] Processing credential {i+1}/{len(credentials)}: {username}")
            
            try:
                result = emodal_login(username, password, captcha_api_key, use_vpn)
                result['credential_index'] = i + 1
                results.append(result)
                
            except Exception as e:
                logger.error(f"[{request_id}] Credential {i+1} failed: {str(e)}")
                results.append({
                    "success": False,
                    "error_type": "processing_error",
                    "error_message": str(e),
                    "credential_index": i + 1
                })
        
        # Summary stats
        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful
        
        logger.info(f"[{request_id}] Batch complete: {successful} successful, {failed} failed")
        
        return jsonify({
            "success": successful > 0,
            "results": results,
            "summary": {
                "total": len(results),
                "successful": successful,
                "failed": failed
            },
            "request_id": request_id,
            "timestamp": timestamp
        })
        
    except Exception as e:
        logger.error(f"[{request_id}] Batch API error: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Batch processing error: {str(e)}",
            "request_id": request_id
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error_type": "endpoint_not_found",
        "error_message": "Endpoint not found",
        "available_endpoints": [
            "POST /login - Single login",
            "POST /login/batch - Batch login",
            "GET /health - Health check"
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        "success": False,
        "error_type": "internal_server_error",
        "error_message": "Internal server error occurred"
    }), 500


if __name__ == '__main__':
    print("🚀 E-Modal Authentication API")
    print("=" * 50)
    print("✅ Professional login automation")
    print("✅ VPN integration support") 
    print("✅ reCAPTCHA handling with fallbacks")
    print("✅ Comprehensive error detection")
    print("✅ Session token extraction")
    print("✅ Batch processing support")
    print("=" * 50)
    print("📍 Endpoints:")
    print("  POST /login - Single authentication")
    print("  POST /login/batch - Batch authentication")
    print("  GET /health - Health check")
    print("=" * 50)
    print("🔗 Starting server on http://localhost:5000")
    
    # Ensure log directory exists
    os.makedirs('logs', exist_ok=True)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False  # Set to False for production
    )

