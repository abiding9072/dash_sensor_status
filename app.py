import os
import boto3
import requests
from dotenv import load_dotenv
from twilio.rest import Client
from datetime import datetime, timezone
from flask import Flask, render_template, make_response

load_dotenv()

# NMS
LIBRENMS_API_URL = os.getenv("LIBRENMS_API_URL")
LIBRENMS_API_TOKEN = os.getenv("LIBRENMS_API_TOKEN")

# HEALTHCHECKS
HEALTHCHECKS_PINGS_API_KEY = os.getenv("HEALTHCHECKS_PINGS_API_KEY")
HEALTHCHECKS_SCRIPTS_API_KEY = os.getenv("HEALTHCHECKS_SCRIPTS_API_KEY")

# VPN EXP
MULLVAD_ACC_ID = os.getenv("MULLVAD_ACC_ID")

# TWILIO SMS
TWIL_SMS_ACCOUNT_SID = os.getenv("TWIL_SMS_ACCOUNT_SID")
TWIL_SMS_AUTH_TOKEN = os.getenv("TWIL_SMS_AUTH_TOKEN")

# SMTP2GO
SMTP_API_KEY = os.getenv("SMTP_API_KEY")

# S3
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_REGION = os.getenv("S3_REGION")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

app = Flask(__name__)

# global vars
current_day = None
vpn_exp_day = None
s3_usage = None

def set_curr_date():
    return datetime.now().date()

def get_alerts():
    try:
        HEADERS = {"X-Auth-Token": LIBRENMS_API_TOKEN}
        response = requests.get(f"{LIBRENMS_API_URL}/alerts", headers=HEADERS, timeout=10)
        response.raise_for_status()
        alerts = response.json().get("alerts", [])
        return [alert for alert in alerts if (alert.get("state") == 1 and alert.get("open") == 1)]
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return "error"


def get_device_display(device_id):
    try:
        HEADERS = {"X-Auth-Token": LIBRENMS_API_TOKEN}
        response = requests.get(f"{LIBRENMS_API_URL}/devices/{device_id}", headers=HEADERS, timeout=5)
        response.raise_for_status()
        return response.json()["devices"][0]["display"]
    except Exception:
        return "Unknown System"

def get_failed_services(device_id):
    try:
        HEADERS = {"X-Auth-Token": LIBRENMS_API_TOKEN}
        response = requests.get(f"{LIBRENMS_API_URL}/services?state=2", headers=HEADERS, timeout=5)
        services_list = []
        for service in response.json()['services'][0]:
            if int(service['device_id']) == int(device_id):
                services_list.append(f"({service['service_type']}) {service['service_name']}")
        return services_list
    except Exception:
        return []

def get_down_healthchecks():
    try:
        headers = {
            "X-Api-Key": HEALTHCHECKS_SCRIPTS_API_KEY
        }
        response = requests.get("https://checks.noot.cc/api/v3/checks/?tag=scripts", headers=headers, timeout=5)
        script_checks = response.json().get("checks", [])
        headers = {
            "X-Api-Key": HEALTHCHECKS_PINGS_API_KEY
        }
        response = requests.get("https://checks.noot.cc/api/v3/checks/?tag=pings", headers=headers, timeout=5)
        ping_checks = response.json().get("checks", [])

        x = 0
        for check in script_checks:
            if check['status'] == 'down':
                x += 1
        for check in ping_checks:
            if check['status'] == 'down':
                x += 1
        return x
    except Exception as e:
        print(f"Healthchecks API error: {e}")
        return "?"


def get_twilio_balance():
    try:
        if not TWIL_SMS_ACCOUNT_SID or not TWIL_SMS_AUTH_TOKEN:
            raise ValueError("Twilio credentials not set in environment")

        client = Client(TWIL_SMS_ACCOUNT_SID, TWIL_SMS_AUTH_TOKEN)
        balance = client.api.account.balance.fetch()
        rounded_bal = f"${float(balance.balance):.1f}"
        return rounded_bal  # Returns balance as a number
    except Exception as e:
        print(f"Error fetching Twilio balance: {e}")
        return "?"

def get_mullvad_days_left(account_number):
    try:
        url = f"https://api.mullvad.net/public/accounts/v1/{account_number}/"
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()
        expiry_str = data.get("expiry")

        if not expiry_str:
            raise ValueError("No expiration info in response")

        expiry_date = datetime.fromisoformat(expiry_str.replace("Z", "+00:00")).date()
        today = datetime.now(timezone.utc).date()

        days_left = (expiry_date - today).days
        return max(days_left, 0)
    except Exception as e:
        print(f"Error fetching Mullvad expiration: {e}")
        return "?"

def bytes_to_human_readable(num_bytes):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(num_bytes)
    for unit in units:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"

def get_S3_bucket_usage():
    s3 = boto3.client(
        "s3",
        region_name=S3_REGION,
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY
    )
    total_size = 0
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME):
            contents = page.get("Contents", [])
            for obj in contents:
                total_size += obj.get("Size", 0)
    except Exception as e:
        print(f"Error fetching Wasabi bucket usage: {e}")
        return "?"
    readable = bytes_to_human_readable(total_size)
    return readable

def get_smtp2go_daily_usage():
    headers = {
        'Content-Type': 'application/json',
        'X-Smtp2go-Api-Key': SMTP_API_KEY
    }
    try:
        resp = requests.post(
            'https://api.smtp2go.com/v3/stats/email_cycle',
            headers=headers,
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json().get('data', {})
    except Exception as e:
        print(f"Error fetching SMTP2GO usage: {e}")
        return "?", "?", "?"

    total_sent = data.get('cycle_used', 0)
    total_quota = data.get('cycle_remaining', 0)
    timestamp = data.get('cycle_end', "")
    dt = datetime.fromisoformat(timestamp)
    renewal = dt.strftime("%m/%d")
    sent_ratio = f"{total_sent} / {total_quota}"

    return sent_ratio, renewal


@app.route("/health", methods=["GET"])
def health():
    return make_response("NMS Dashboard is UP!", 200)


@app.route("/")
def status_page():
    global current_day
    global vpn_exp_day
    global s3_usage

    now = datetime.now().date()

    alerts = get_alerts()

    # healthchecks
    down_checks = get_down_healthchecks()

    # One-time vars
    if now != current_day:
        print(f"Fetching once-per-day data")
        current_day = set_curr_date()
        vpn_exp = get_mullvad_days_left(MULLVAD_ACC_ID)
        vpn_exp_day = vpn_exp
        s3_usage = get_S3_bucket_usage()
        
    # Twilio SMS Balance
    twil_bal = get_twilio_balance()

    # SMTP2GO sent/remaining
    smtp_data = get_smtp2go_daily_usage()
    smtp_ratio = smtp_data[0]
    smtp_renewal = smtp_data[1]

    stats_bar = [
        {"title": "DOWN CHECKS", "value": down_checks},
        {"title": f"SMTP | exp: ({smtp_renewal})", "value": smtp_ratio},
        {"title": "BBB2 USAGE", "value": s3_usage},
        {"title": "VPN EXP DAYS", "value": vpn_exp_day},
        {"title": "TWIL BAL", "value": twil_bal},
    ]

    # NMS alerts
    if alerts == "error":
        status = "red"
        message = f"ERROR"
        alert_details = "Unable to fetch LibreNMS.."

        return render_template("index.html", status=status, message=message, alerts=alert_details)
    else:
        count = len(alerts)

        if count == 0:
            status = "green"
            message = "No alerts!"
            alert_details = []
        elif count <= 3:
            alert_details = []
            for alert in alerts:
                device_id = alert.get("device_id")
                if "service" in str(alert.get("name").lower()):
                    services_list = get_failed_services(device_id)
                    if services_list:
                        alert_details.append({
                            "hostname": get_device_display(device_id),
                            "rule": alert.get("name", "Unknown"),
                            "services": services_list
                        })
                    else:
                        count = count - 1
                else:
                    alert_details.append({
                        "hostname": get_device_display(device_id),
                        "rule": alert.get("name", "Unknown")
                    })

            if count > 0:
                status = "orange" if count <= 2 else "red"
                message = f"{count} alert{'s!' if count > 1 else '!'}"
            else:
                status = "green"
                message = "No alerts!"
        else:
            status = "red"
            message = f"{count} alerts!"
            alert_details = "MULTIPLE FAILURES!\nCheck the LibreNMS dashboard for details."

        if status == "green" and not (down_checks == 0 and vpn_exp_day > 7 and float(str(twil_bal).replace("$", "")) > 3):
            message = "One or more items below require attention."
            status = "orange"

    return render_template("index.html", status=status, message=message, alerts=alert_details, stats=stats_bar)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9090)
