import logging
import os
import csv
import json
import requests
from datetime import datetime, timedelta, timezone, time
from typing import Tuple, Dict, Any, List

# --- 1. Centralized Logger ---
def setup_logging(level=logging.INFO):
    """Configures the root logger once."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | [%(levelname)s] | %(name)s | %(funcName)s(%(filename)s:%(lineno)d): %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def get_logger(name: str):
    """Returns a logger instance for the specific module."""
    return logging.getLogger(name)

logger = get_logger(__name__)

# --- 2. I/O Operations ---
def ensure_output_dir(directory: str = "output"):
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_to_json(data: Dict[str, Any], filename: str):
    """Saves the results to a JSON file in the output directory."""
    ensure_output_dir()
    path = os.path.join("output", filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"✅ Saved JSON to {path}")
    except Exception as e:
        logger.error(f"Failed to save JSON: {e}")

def save_to_csv(flat_data: List[Dict[str, Any]], filename: str):
    """Saves the results to a CSV file in the output directory."""
    ensure_output_dir()
    if not flat_data:
        logger.warning("⚠️ No data available to save to CSV.")
        return

    path = os.path.join("output", filename)
    try:
        # Get headers from the first dictionary keys
        headers = flat_data[0].keys()
        
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(flat_data)
        logger.info(f"✅ Saved CSV to {path}")
    except Exception as e:
        logger.error(f"Failed to save CSV: {e}")

# --- Webhook Logic ---
def send_webhook(url: str, payload: Dict[str, Any]):
    """
    Sends the analysis results to the specified Webhook URL.
    """
    if not url:
        logger.warning("⚠️ Webhook URL is empty. Skipping sending.")
        return

    logger.info(f"🚀 Sending payload to Webhook...")
    
    try:
        # We send the data as a JSON POST request
        response = requests.post(
            url, 
            json=payload, 
            headers={"Content-Type": "application/json"},
            timeout=30  # 30-second timeout to prevent hanging
        )
        
        # Check for HTTP errors (4xx or 5xx)
        response.raise_for_status()
        
        logger.info(f"✅ Webhook sent successfully! (Status: {response.status_code})")

    except requests.exceptions.Timeout:
        logger.error("❌ Webhook failed: Request timed out.")
    except requests.exceptions.ConnectionError:
        logger.error("❌ Webhook failed: Connection refused or DNS failure.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ Webhook failed: Server returned error {e.response.status_code}.")
    except Exception as e:
        logger.error(f"❌ Webhook failed: Unexpected error {e}")