
import os
import json
import logging
import time
import requests
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# Device Info
DEVICE_ID = "lufa_farms_account"
DEVICE_NAME = "Lufa Farms"
MANUFACTURER = "Lufa Farms"

class LufaMQTTClient:
    def __init__(self, config):
        self.config = config
        self.mqtt_client = None
        self.connected = False
        
    def connect(self):
        """Connects to the MQTT broker."""
        host = self.config.get('mqtt_host')
        port = self.config.get('mqtt_port')
        username = self.config.get('mqtt_username')
        password = self.config.get('mqtt_password')
        
        # Check for service injection if manual config is missing/empty
        if not host:
            logger.info("No manual MQTT host configured. Checking Supervisor API for MQTT service...")
            service_config = self._get_supervisor_mqtt_config()
            if service_config:
                host = service_config.get('host')
                port = service_config.get('port')
                username = service_config.get('username')
                password = service_config.get('password')
                logger.info(f"Discovered MQTT config from Supervisor: {host}:{port}")
            
        if not host:
            logger.warning("No MQTT configuration found. MQTT features will be disabled.")
            return False

        try:
            if port:
                port = int(port)
            else:
                port = 1883

            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="lufa_farms_addon")
            
            if username and password:
                self.mqtt_client.username_pw_set(username, password)
                
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            
            logger.info(f"Connecting to MQTT Broker at {host}:{port}...")
            self.mqtt_client.connect(host, port, 60)
            self.mqtt_client.loop_start()
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def _get_supervisor_mqtt_config(self):
        """Fetches MQTT configuration from the Supervisor API."""
        token = os.environ.get('SUPERVISOR_TOKEN')
        if not token:
            logger.warning("SUPERVISOR_TOKEN not found. Cannot query Supervisor API.")
            return None
            
        url = "http://supervisor/services/mqtt"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data.get('result') == 'ok':
                    return data.get('data')
            elif response.status_code == 404:
                 logger.warning("MQTT service not found in Supervisor (is Mosquitto installed/running?)")
            
            logger.debug(f"Supervisor API returned {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error querying Supervisor API: {e}")
            
        return None

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("Connected to MQTT Broker!")
            self.connected = True
            self._publish_discovery_config()
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None): # Added properties=None for v2 compatibility
        logger.warning("Disconnected from MQTT Broker")
        self.connected = False

    def _publish_discovery_config(self):
        """Publishes Home Assistant MQTT Discovery payloads."""
        logger.info("Publishing MQTT Discovery payloads...")
        
        sensors = [
            {
                "id": "status",
                "name": "Order Status",
                "icon": "mdi:truck-delivery",
                "value_template": "{{ value_json.status }}"
            },
            {
                "id": "eta",
                "name": "ETA",
                "icon": "mdi:clock-outline",
                "value_template": "{{ value_json.eta }}"
            },
            {
                "id": "stops_before",
                "name": "Stops Before",
                "icon": "mdi:map-marker-path",
                "value_template": "{{ value_json.stops_before }}",
                "unit_of_measurement": "stops"
            },
            {
                "id": "order_amount",
                "name": "Order Amount",
                "icon": "mdi:cash",
                "value_template": "{{ value_json.order_amount }}"
            },
            {
                "id": "order_id",
                "name": "Order ID",
                "icon": "mdi:identifier",
                "value_template": "{{ value_json.order_id }}"
            }
        ]
        
        for sensor in sensors:
            unique_id = f"{DEVICE_ID}_{sensor['id']}"
            topic = f"homeassistant/sensor/{DEVICE_ID}/{sensor['id']}/config"
            
            payload = {
                "name": sensor['name'],
                "unique_id": unique_id,
                "state_topic": f"lufa_farms/{DEVICE_ID}/state",
                "value_template": sensor['value_template'],
                "icon": sensor['icon'],
                "device": {
                    "identifiers": [DEVICE_ID],
                    "name": DEVICE_NAME,
                    "manufacturer": MANUFACTURER
                }
            }
            
            if "unit_of_measurement" in sensor:
                payload["unit_of_measurement"] = sensor["unit_of_measurement"]
                
            self.mqtt_client.publish(topic, json.dumps(payload), retain=True)

    def publish_state(self, details, order_id):
        """Publishes the current state to the state topic."""
        if not self.connected or not self.mqtt_client:
            return

        topic = f"lufa_farms/{DEVICE_ID}/state"
        
        # Flatten details for easier template access if needed, or just dump it
        # We need to ensure all keys used in templates are present
        payload = {
            "status": details.get('status', 'Unknown'),
            "eta": details.get('eta', 'Unknown'),
            "stops_before": details.get('stops_before', 0),
            "order_amount": details.get('order_amount', '0.00 $'),
            "order_id": order_id
        }
        
        self.mqtt_client.publish(topic, json.dumps(payload), retain=True)
        logger.debug(f"Published state update to {topic}")

