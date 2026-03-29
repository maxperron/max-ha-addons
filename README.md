# Max's Home Assistant Add-ons

This repository contains Home Assistant add-ons that I have developed for my personal use.

## ⚠️ Important Disclaimers

> [!CAUTION]
> **Use at your own risk.**
> These add-ons are created specifically for my own use cases. They may not be suitable for general use and are provided "as is" without any warranty.

## Add-ons

### Family Expenses Tracker
A simple addon designed to help track family expenses within Home Assistant.

### Lufa Farms
Track your Lufa Farms deliveries directly in Home Assistant.

#### Dependencies
This addon requires an MQTT broker to be available (e.g., the Mosquitto broker addon). It will automatically discover and connect to the broker using Home Assistant's internal service discovery.

#### Entities
The addon creates a device named **Lufa Farms** with the following sensors:
- **Order Status**: Current status of your delivery.
- **ETA**: Estimated time of arrival.
- **Stops Before**: Number of stops before your delivery.
- **Order Amount**: Total amount of the current order.
- **Order ID**: The ID of the current order being tracked.

> [!WARNING]
> **Not supported by Lufa Farms.**
> This addon is a third-party project and is **NOT** supported by or affiliated with Lufa Farms.
> **Use with caution:** usage of this addon might violate Lufa Farms' Terms and Conditions. Proceed at your own discretion.
