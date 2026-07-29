import os
import sys
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error

print("=== Starting Yegna Bet Python-Node Application Wrapper ===")

INTERNAL_PORT = 3000
_node_process = None

def ensure_node_app_built():
    if not os.path.exists("dist/server.cjs"):
        print("dist/server.cjs not found. Building Node.js server bundle...")
        subprocess.run(["npm", "install"], check=True)
        subprocess.run(["npm", "run", "build"], check=True)

def start_internal_node():
    global _node_process
    if _node_process is not None and _node_process.poll() is None:
        return

    ensure_node_app_built()

    env = os.environ.copy()
    env["PORT"] = str(INTERNAL_PORT)
    env["NODE_ENV"] = "production"

    print(f"Launching internal Node server on port {INTERNAL_PORT}...")
    _node_process = subprocess.Popen(["node", "dist/server.cjs"], env=env)

    # Wait until internal Node server is accepting connections
    health_url = f"http://127.0.0.1:{INTERNAL_PORT}/api/health"
    for i in range(40):
        try:
            req = urllib.request.Request(health_url)
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    print("Internal Node server is healthy and ready!")
                    return
        except Exception:
            time.sleep(0.25)
    print("Notice: Proceeding after internal port health check wait.")

# Pre-initialize internal Node server when imported
start_internal_node()

# WSGI Server function for Gunicorn (main:server)
def server(environ, start_response):
    start_internal_node()

    method = environ.get('REQUEST_METHOD', 'GET')
    path_info = environ.get('PATH_INFO', '')
    query_string = environ.get('QUERY_STRING', '')

    url = f"http://127.0.0.1:{INTERNAL_PORT}{path_info}"
    if query_string:
        url += f"?{query_string}"

    headers = {}
    for key, val in environ.items():
        if key.startswith('HTTP_'):
            header_name = key[5:].replace('_', '-').title()
            headers[header_name] = val
        elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            if val:
                header_name = key.replace('_', '-').title()
                headers[header_name] = val

    content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
    body = environ['wsgi.input'].read(content_length) if content_length > 0 else None

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req) as resp:
            status = f"{resp.status} {resp.reason}"
            resp_headers = [(k, v) for k, v in resp.headers.items() if k.lower() != 'transfer-encoding']
            start_response(status, resp_headers)
            return [resp.read()]
    except urllib.error.HTTPError as e:
        status = f"{e.code} {e.reason}"
        resp_headers = [(k, v) for k, v in e.headers.items() if k.lower() != 'transfer-encoding']
        start_response(status, resp_headers)
        return [e.read()]
    except Exception as e:
        status = "500 Internal Server Error"
        start_response(status, [('Content-Type', 'text/plain')])
        return [f"Proxy Error: {e}".encode('utf-8')]

if __name__ == '__main__':
    port = os.environ.get("PORT", "10000")
    ensure_node_app_built()
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["NODE_ENV"] = "production"
    os.execvp("node", ["node", "dist/server.cjs"])
