import http.server
import socketserver
import json
import os
import time

try:
    import yfinance as yf
except ImportError:
    yf = None

HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', 8080))

CACHE: dict = {}
CACHE_TTL = 300  # seconds


def compute_adr(ticker: str) -> dict:
    now = time.time()
    entry = CACHE.get(ticker)
    if entry and now < entry['expires']:
        return entry['data']

    if yf is None:
        raise RuntimeError('yfinance is not installed')

    try:
        hist = yf.Ticker(ticker).history(period='1mo')
    except Exception as e:
        raise ValueError(f'ticker not found: {e}')

    # yfinance appends a row for the unsettled session with NaN OHLC (volume only);
    # drop it so the last row is always a completed bar.
    hist = hist.dropna(subset=['Open', 'High', 'Low', 'Close'])
    if hist.empty or len(hist) < 5:
        raise ValueError('ticker not found or insufficient data')

    df = hist.tail(20)
    adr_dollar = float((df['High'] - df['Low']).mean())
    adr_pct = float(((df['High'] - df['Low']) / df['Close'] * 100).mean())
    day_low = float(df.iloc[-1]['Low'])
    day_high = float(df.iloc[-1]['High'])
    current_price = float(df.iloc[-1]['Close'])

    data = {
        'ticker': ticker,
        'adr': round(adr_dollar, 4),
        'adr_pct': round(adr_pct, 4),
        'day_low': round(day_low, 4),
        'day_high': round(day_high, 4),
        'current_price': round(current_price, 4),
    }
    CACHE[ticker] = {'expires': now + CACHE_TTL, 'data': data}
    return data


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f'[{self.address_string()}] {format % args}')

    def _send_json(self, data: dict, status: int = 200) -> None:
        try:
            # allow_nan=False: NaN/Infinity are not valid JSON and would make the
            # browser's res.json() throw on an otherwise-200 response.
            body = json.dumps(data, allow_nan=False).encode()
        except ValueError as e:
            print(f'Refusing to send non-JSON-serializable payload: {e} -- {data}')
            body = json.dumps({'error': 'internal server error'}).encode()
            status = 500
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]  # strip query string

        if path.startswith('/api/adr/'):
            ticker = path[len('/api/adr/'):].strip('/').upper()
            if not ticker:
                self._send_json({'error': 'ticker required'}, 400)
                return
            try:
                data = compute_adr(ticker)
                self._send_json(data)
            except ValueError as e:
                self._send_json({'error': str(e)}, 404)
            except Exception as e:
                self._send_json({'error': 'internal server error'}, 500)
                print(f'Error fetching ADR for {ticker}: {e}')
        else:
            self._send_json({'error': 'not found'}, 404)


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    with ThreadedServer((HOST, PORT), Handler) as httpd:
        print(f'Server running on http://{HOST}:{PORT}')
        httpd.serve_forever()
