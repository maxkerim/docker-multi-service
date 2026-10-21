"""Сервис web: отдаёт страницу, которая ходит в API через шлюз."""
from flask import Flask, Response

PAGE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Docker multi-service</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 560px; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.4rem; }
    form { display: flex; gap: .5rem; margin: 1rem 0; }
    input { flex: 1; padding: .5rem; }
    button { padding: .5rem 1rem; cursor: pointer; }
    #status { color: #555; }
    #error { color: #b00020; }
  </style>
</head>
<body>
  <h1>Docker multi-service</h1>
  <p id="status">Проверяю API...</p>
  <p>Посещений: <strong id="visits">-</strong></p>

  <form id="form">
    <input id="name" maxlength="100" placeholder="Новая запись" required>
    <button type="submit">Добавить</button>
  </form>
  <p id="error"></p>
  <ul id="items"></ul>

  <script>
    const $ = (id) => document.getElementById(id);

    async function api(path, options) {
      const resp = await fetch(path, options);
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.error || JSON.stringify(body));
      return body;
    }

    async function loadStatus() {
      try {
        const resp = await fetch('/api/health');
        const body = await resp.json();
        $('status').textContent = 'API: ' + (resp.ok ? 'работает' : 'проблемы') + ' (' + JSON.stringify(body) + ')';
      } catch (e) {
        $('status').textContent = 'API недоступен';
      }
    }

    async function loadVisits() {
      try { $('visits').textContent = (await api('/api/visits')).visits; }
      catch (e) { $('visits').textContent = 'н/д'; }
    }

    async function loadItems() {
      try {
        const data = await api('/api/items');
        $('items').replaceChildren(...data.items.map((i) => {
          const li = document.createElement('li');
          li.textContent = i.name;
          return li;
        }));
      } catch (e) { $('error').textContent = e.message; }
    }

    $('form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      $('error').textContent = '';
      try {
        await api('/api/items', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: $('name').value })
        });
        $('name').value = '';
        loadItems();
      } catch (e) { $('error').textContent = e.message; }
    });

    loadStatus(); loadVisits(); loadItems();
  </script>
</body>
</html>
"""


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return Response(PAGE, mimetype="text/html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
