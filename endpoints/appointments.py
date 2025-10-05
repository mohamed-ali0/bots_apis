"""
Appointments Endpoint
Flask blueprint for appointment booking operations.
"""

import os
import time
import shutil
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory

from config import get_config_from_request, validate_appointment_request, get_screenshot_dir
from models.response_models import success_response, error_response, session_continuation_response
from handlers.session_handler import SessionManager
from operations.appointment_operations import AppointmentOperations

# Create Blueprint
bp = Blueprint('appointments', __name__)

# Global session manager
session_manager = SessionManager()


@bp.route('/check_appointments', methods=['POST'])
def check_appointments():
    """
    Check available appointment times without submitting.
    Supports session continuation for missing fields.
    """
    try:
        data = request.get_json()
        if not data:
            return error_response("No JSON data provided", 400)
        
        # Extract configuration
        config = get_config_from_request(data)
        
        # Validate request
        is_valid, error_msg = validate_appointment_request(data)
        if not is_valid:
            return error_response(error_msg, 400)
        
        # Check if continuing existing session
        session_id = data.get('session_id')
        appt_session = None
        
        if session_id:
            print(f"🔄 Continuing appointment session: {session_id}")
            appt_session = session_manager.get_appointment_session(session_id)
            if not appt_session:
                return error_response(
                    "Session not found or expired. Please start a new request.",
                    404
                )
            appt_session.update_last_used()
        else:
            # Create new browser session
            print(f"🆕 Creating new appointment session for user: {config['username']}")
            try:
                browser_session = session_manager.create_browser_session(
                    username=config['username'],
                    password=config['password'],
                    captcha_api_key=config['captcha_api_key'],
                    headless=config['headless'],
                    download_dir=config.get('download_dir'),
                    timeout=config['timeout']
                )
            except Exception as auth_error:
                return error_response(f"Authentication failed: {auth_error}", 401)
            
            # Create appointment session
            appt_session = session_manager.create_appointment_session(
                browser_session=browser_session,
                current_phase=1,
                phase_data={}
            )
        
        # Get operations instance
        screenshot_dir = get_screenshot_dir(
            config['screenshot_dir'],
            appt_session.session_id
        )
        operations = AppointmentOperations(
            driver=appt_session.browser_session.driver,
            screenshot_dir=screenshot_dir
        )
        
        # Navigate to appointment page (only if Phase 1)
        if appt_session.current_phase == 1:
            result = operations.navigate_to_appointment()
            if not result["success"]:
                return error_response(
                    f"Failed to navigate to appointment page: {result.get('error')}",
                    500
                )
        
        # PHASE 1: Trucking Company, Terminal, Move Type, Container
        if appt_session.current_phase == 1:
            print("\n" + "="*70)
            print("📋 PHASE 1: Trucking Company, Terminal, Move Type, Container")
            print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 1 to fully load...")
            time.sleep(5)
            print("✅ Phase 1 ready")
            
            trucking_company = data.get('trucking_company')
            terminal = data.get('terminal')
            move_type = data.get('move_type')
            container_id = data.get('container_id')
            
            # Check for missing fields
            missing = []
            if not trucking_company: missing.append('trucking_company')
            if not terminal: missing.append('terminal')
            if not move_type: missing.append('move_type')
            if not container_id: missing.append('container_id')
            
            if missing:
                return session_continuation_response(
                    session_id=appt_session.session_id,
                    current_phase=1,
                    missing_fields=missing
                )
            
            # Fill Phase 1 fields
            result = operations.select_dropdown_by_text("Trucking", trucking_company)
            if not result["success"]:
                return error_response(f"Phase 1 - Trucking: {result['error']}", 500)
            
            result = operations.select_dropdown_by_text("Terminal", terminal)
            if not result["success"]:
                return error_response(f"Phase 1 - Terminal: {result['error']}", 500)
            
            result = operations.select_dropdown_by_text("Move", move_type)
            if not result["success"]:
                return error_response(f"Phase 1 - Move Type: {result['error']}", 500)
            
            result = operations.fill_container_number(container_id)
            if not result["success"]:
                return error_response(f"Phase 1 - Container: {result['error']}", 500)
            
            # Click Next with retry logic
            max_retries = 2
            for attempt in range(max_retries):
                result = operations.click_next_button(1)
                if result["success"]:
                    break
                elif result.get("needs_retry") and attempt < max_retries - 1:
                    print(f"  🔄 Retrying Next button after re-filling form...")
                    # Re-fill form fields
                    operations.select_dropdown_by_text("Trucking", trucking_company)
                    operations.select_dropdown_by_text("Terminal", terminal)
                    operations.select_dropdown_by_text("Move", move_type)
                    operations.fill_container_number(container_id)
                else:
                    return error_response(f"Phase 1 - Next: {result['error']}", 500)
            
            appt_session.current_phase = 2
            print("✅ Phase 1 completed successfully")
        
        # PHASE 2: Container Selection, PIN, Truck Plate, Chassis
        if appt_session.current_phase == 2:
            print("\n" + "="*70)
            print("📋 PHASE 2: Container Selection, PIN, Truck Plate, Chassis")
            print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 2 to fully load...")
            time.sleep(5)
            print("✅ Phase 2 ready")
            
            pin_code = data.get('pin_code')
            truck_plate = data.get('truck_plate')
            own_chassis = data.get('own_chassis', False)
            
            # Check for missing required fields
            missing = []
            if not truck_plate: missing.append('truck_plate')
            
            if missing:
                return session_continuation_response(
                    session_id=appt_session.session_id,
                    current_phase=2,
                    missing_fields=missing
                )
            
            # Fill Phase 2 fields
            result = operations.select_container_checkbox()
            if not result["success"]:
                return error_response(f"Phase 2 - Checkbox: {result['error']}", 500)
            
            if pin_code:
                result = operations.fill_pin_code(pin_code)
                if not result["success"] and not result.get("not_found"):
                    return error_response(f"Phase 2 - PIN: {result['error']}", 500)
            
            result = operations.fill_truck_plate(truck_plate, allow_any_if_missing=True)
            if not result["success"]:
                return error_response(f"Phase 2 - Truck Plate: {result['error']}", 500)
            
            result = operations.toggle_own_chassis(own_chassis)
            if not result["success"]:
                return error_response(f"Phase 2 - Own Chassis: {result['error']}", 500)
            
            # Click Next with retry logic
            max_retries = 2
            for attempt in range(max_retries):
                result = operations.click_next_button(2)
                if result["success"]:
                    break
                elif result.get("needs_retry") and attempt < max_retries - 1:
                    print(f"  🔄 Retrying Next button after re-filling form...")
                    # Re-fill form fields
                    operations.fill_truck_plate(truck_plate, allow_any_if_missing=True)
                    operations.toggle_own_chassis(own_chassis)
                else:
                    return error_response(f"Phase 2 - Next: {result['error']}", 500)
            
            appt_session.current_phase = 3
            print("✅ Phase 2 completed successfully")
        
        # PHASE 3: Get Available Times
        if appt_session.current_phase == 3:
            print("\n" + "="*70)
            print("📋 PHASE 3: Retrieving Available Appointment Times")
            print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 3 to fully load...")
            time.sleep(5)
            print("✅ Phase 3 ready")
            
            result = operations.get_available_appointment_times()
            if not result["success"]:
                return error_response(
                    f"Phase 3 failed: {result['error']}",
                    500,
                    session_id=appt_session.session_id,
                    current_phase=3
                )
            
            available_times = result["available_times"]
            print("✅ Phase 3 completed successfully")
            print(f"✅ Found {len(available_times)} available appointment times")
        
        # Create debug bundle if requested
        bundle_url = None
        if config['debug']:
            try:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bundle_name = f"{appt_session.session_id}_{ts}_check_appointments.zip"
                bundle_path = os.path.join(config['download_dir'], bundle_name)
                
                # Create ZIP of screenshots
                shutil.make_archive(
                    bundle_path.replace('.zip', ''),
                    'zip',
                    screenshot_dir
                )
                
                # Generate public URL
                bundle_url = f"http://{request.host}/files/{bundle_name}"
                print(f"\n📦 DEBUG BUNDLE CREATED")
                print(f"{'='*70}")
                print(f" Public URL: {bundle_url}")
                print(f"{'='*70}\n")
            except Exception as e:
                print(f"⚠️ Failed to create debug bundle: {e}")
        
        # Close appointment session (keep browser session alive)
        session_manager.close_appointment_session(appt_session.session_id)
        
        # Build response
        response_data = {
            "available_times": available_times,
            "count": len(available_times),
            "session_id": appt_session.session_id
        }
        
        if bundle_url:
            response_data["debug_bundle"] = bundle_url
        
        return success_response(response_data)
    
    except Exception as e:
        print(f"❌ Error in check_appointments: {e}")
        import traceback
        traceback.print_exc()
        return error_response(f"Internal server error: {e}", 500)


@bp.route('/make_appointment', methods=['POST'])
def make_appointment():
    """
    Make appointment (placeholder - will submit).
    ⚠️ NOT IMPLEMENTED YET - Use /check_appointments for testing.
    """
    return error_response(
        "Endpoint not implemented yet. Use /check_appointments for testing.",
        501
    )

