import os
import json
import time
import logging
import sys
from client import LufaClient
from mqtt_client import LufaMQTTClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("lufa_farms")

def get_config():
    """Read configuration from Home Assistant options."""
    options_path = '/data/options.json'
    if os.path.exists(options_path):
        import json
        with open(options_path, 'r') as f:
            return json.load(f)
    return {}

def load_s6_environment():
    """Manually load S6 environment variables since we are not using with-contenv."""
    s6_env_dir = "/var/run/s6/container_environment"
    if os.path.isdir(s6_env_dir):
        logger.info(f"Loading S6 environment from {s6_env_dir}")
        for var_name in os.listdir(s6_env_dir):
            try:
                with open(os.path.join(s6_env_dir, var_name), 'r') as f:
                    value = f.read().strip()
                # Only set if not already set (preserve runtime overrides)
                if var_name not in os.environ:
                    os.environ[var_name] = value
            except Exception as e:
                logger.warning(f"Failed to load env var {var_name}: {e}")
    else:
        logger.warning(f"S6 environment directory {s6_env_dir} not found.")

def main():
    # Load S6 env vars first
    load_s6_environment()
    
    logger.info("Starting Lufa Farms Add-on")
    
    # DEBUG: Log available environment variables
    logger.info(f"Environment variables keys: {list(os.environ.keys())}")
    
    if 'SUPERVISOR_TOKEN' in os.environ:
        logger.info("SUPERVISOR_TOKEN is present.")
    else:
        logger.warning("SUPERVISOR_TOKEN is MISSING.")
        
    config = get_config()
    email = config.get('email')
    password = config.get('password')
    
    if not email or not password:
        logger.error("Email and password must be provided in configuration.")
        sys.exit(1)
        
    # Initialize Lufa Client
    lufa_client = LufaClient(email, password)
    
    # Initialize MQTT Client
    mqtt_client = LufaMQTTClient(config)
    if not mqtt_client.connect():
        logger.warning("Continuing without MQTT (Check configuration or broker status).")
    
    # Scan interval in seconds (default 15 mins)
    scan_interval = config.get('scan_interval', 900)
    
    # Track last update for off-day keep-alive
    last_update_date = None
    
    while True:
        try:
            # Determine if we should update based on delivery days
            import datetime
            today = datetime.date.today()
            day_name = today.strftime("%A")
            delivery_days = config.get('delivery_days', [])
            
            should_update = False
            
            if not delivery_days:
                # No specific days configured, always update
                should_update = True
            elif day_name in delivery_days:
                # Today is a delivery day, update
                should_update = True
            elif last_update_date != today:
                # Off-day, but run once per day for keep-alive
                logger.info(f"Off-day ({day_name}): Performing daily keep-alive update.")
                should_update = True
            else:
                # Off-day and already updated
                logger.info(f"Off-day ({day_name}): Skipping update (next daily check tomorrow).")
                should_update = False

            if should_update:
                logger.info("Fetching update...")
                order_id = lufa_client.get_current_order_id()
                
                if order_id:
                    logger.info(f"Found active Order ID: {order_id}")
                    details = lufa_client.get_order_details(order_id)
                    if details:
                        logger.info("Order details retrieved successfully.")
                        status = details.get('status')
                        eta = details.get('eta')
                        amount = details.get('order_amount')
                        
                        logger.info(f"Status: {status}, ETA: {eta}, Amount: {amount}")
                        
                        # Publish via MQTT
                        mqtt_client.publish_state(details, order_id)
                else:
                    logger.info("No active order found.")
                    # Optionally clear state or publish empty/idle state
                    # mqtt_client.publish_state({'status': 'No Active Order'}, None)
                
                last_update_date = today

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
        logger.info(f"Sleeping for {scan_interval} seconds...")
        time.sleep(scan_interval)

if __name__ == "__main__":
    main()
