from flask import Flask, render_template, request, jsonify
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, FeedbackRequired, PleaseWaitFewMinutes
import threading
import time
import random
import os
import json
import psutil
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sujal_hawk_multi_2026"

state = {"running": False, "sent": 0, "logs": [], "start_time": None}
cfg = {
    "sessionids": [],
    "thread_id": 0,
    "messages": [],
    "group_name": "",
    "delay": 12,
    "name_change_delay": 4,
    "switch_delay": 3,
    "cycle": 35,
    "break_sec": 40
}

DEVICES = [
    {"phone_manufacturer": "Google", "phone_model": "Pixel 8 Pro", "android_version": 15, "android_release": "15.0.0", "app_version": "323.0.0.46.109"},
    {"phone_manufacturer": "Samsung", "phone_model": "SM-S928B", "android_version": 15, "android_release": "15.0.0", "app_version": "324.0.0.41.110"},
    {"phone_manufacturer": "OnePlus", "phone_model": "PJZ110", "android_version": 15, "android_release": "15.0.0", "app_version": "322.0.0.40.108"},
    {"phone_manufacturer": "Xiaomi", "phone_model": "23127PN0CC", "android_version": 15, "android_release": "15.0.0", "app_version": "325.0.0.42.111"},
]

def get_system_stats():
    try:
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
        cpu = psutil.cpu_percent(interval=0.05)
        return f"RAM: {mem_mb:.1f} MB / 512 MB | CPU: {cpu:.1f}%"
    except:
        return "RAM: N/A | CPU: N/A"

def log(msg):
    stats = get_system_stats()
    entry = f"[{time.strftime('%H:%M:%S')}] {stats} | {msg}"
    state["logs"].append(entry)
    if len(state["logs"]) > 500:
        state["logs"] = state["logs"][-500:]

def change_name(cl, thread_id, new_name):
    for attempt in range(3):
        try:
            csrf = cl.private.cookies.get("csrftoken", "")
            cl.private.headers.update({"X-CSRFToken": csrf})
            payload = {
                "doc_id": "29088580780787855",
                "variables": json.dumps({"thread_fbid": str(thread_id), "new_title": new_name})
            }
            r = cl.private.post("https://www.instagram.com/api/graphql/", data=payload, timeout=15)
            if r.status_code == 200:
                return True
        except:
            pass
        time.sleep(5)
    return False

def bomber():
    clients = {}
    for idx, sid in enumerate(cfg["sessionids"]):
        try:
            cl = Client()
            cl.delay_range = [8, 30]
            device = random.choice(DEVICES)
            cl.set_device(device)
            cl.set_user_agent(f"Instagram {device['app_version']} Android (34/15.0.0; 480dpi; 1080x2340; {device['phone_manufacturer']}; {device['phone_model']}; raven; raven; en_US)")
            cl.login_by_sessionid(sid)
            clients[idx] = cl
            log(f"LOGIN SUCCESS → Account #{idx+1}")
        except Exception as e:
            log(f"LOGIN FAILED → Account #{idx+1} | {str(e)[:60]}")

    if not clients:
        log("NO WORKING ACCOUNTS!")
        return

    sent_in_cycle = 0
    current_delay = cfg["delay"]
    acc_keys = list(clients.keys())
    acc_index = 0

    while state["running"]:
        try:
            cl = clients[acc_keys[acc_index]]
            msg = random.choice(cfg["messages"])
            cl.direct_send(msg, thread_ids=[cfg["thread_id"]])
            sent_in_cycle += 1
            state["sent"] += 1
            log(f"SENT #{state['sent']} (Acc #{acc_index+1}) → {msg[:35]}")

            # Name Change
            if cfg["group_name"]:
                new_name = f"{cfg['group_name']} → {datetime.now().strftime('%I:%M:%S %p')}"
                if change_name(cl, cfg["thread_id"], new_name):
                    log(f"NAME CHANGED (Acc #{acc_index+1}) → {new_name}")
                else:
                    log(f"NAME CHANGE FAILED (Acc #{acc_index+1})")

            time.sleep(cfg["name_change_delay"])

            # Switch to next account
            acc_index = (acc_index + 1) % len(acc_keys)
            time.sleep(cfg["switch_delay"])

            if sent_in_cycle >= cfg["cycle"]:
                log(f"BREAK {cfg['break_sec']} SECONDS")
                time.sleep(cfg["break_sec"])
                sent_in_cycle = 0

            time.sleep(current_delay + random.uniform(-2, 3))

        except ChallengeRequired or FeedbackRequired:
            log("Challenge/Feedback → skipping")
            time.sleep(30)
        except PleaseWaitFewMinutes:
            log("Rate limit → waiting 8 min")
            time.sleep(480)
        except Exception as e:
            log(f"SEND FAILED → {str(e)[:50]}")
            time.sleep(8)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    global state
    state["running"] = False
    time.sleep(1)
    state = {"running": True, "sent": 0, "logs": ["MULTI ID BOMBING STARTED"], "start_time": time.time()}

    raw_ids = request.form["sessionids"].strip().split("\n")
    cfg["sessionids"] = [s.strip() for s in raw_ids if s.strip()][:5]  # max 5
    cfg["thread_id"] = int(request.form["thread_id"])
    cfg["messages"] = [m.strip() for m in request.form["messages"].split("\n") if m.strip()]
    cfg["group_name"] = request.form.get("group_name", "").strip()
    cfg["delay"] = float(request.form.get("delay", "12"))
    cfg["name_change_delay"] = float(request.form.get("name_change_delay", "4"))
    cfg["switch_delay"] = float(request.form.get("switch_delay", "3"))
    cfg["cycle"] = int(request.form.get("cycle", "35"))
    cfg["break_sec"] = int(request.form.get("break_sec", "40"))

    threading.Thread(target=bomber, daemon=True).start()
    log(f"STARTED WITH {len(cfg['sessionids'])} ACCOUNTS | Round-Robin Mode")

    return jsonify({"ok": True})

@app.route("/stop")
def stop():
    state["running"] = False
    log("STOPPED BY USER")
    return jsonify({"ok": True})

@app.route("/status")
def status():
    uptime = "00:00:00"
    if state.get("start_time"):
        t = int(time.time() - state["start_time"])
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        uptime = f"{h:02d}:{m:02d}:{s:02d}"
    return jsonify({
        "running": state["running"],
        "sent": state["sent"],
        "uptime": uptime,
        "logs": state["logs"][-100:]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
