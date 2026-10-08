# Sistema de atención al cliente

Sistema local de turnos para cuatro mesas. Los primeros cuatro clientes se asignan a las mesas 1–4. Los siguientes esperan en orden de llegada y se asignan automáticamente a la primera mesa que finalice su atención.

## Funciones

- Generación consecutiva de turnos.
- Cuatro mesas visibles con su turno actual.
- Cola FIFO (primero en llegar, primero en ser atendido).
- Reasignación automática al liberar una mesa.
- Actualización en tiempo real mediante Socket.IO.
- Monitor público y controles de operación en una sola pantalla.
- Estado únicamente en memoria: al reiniciar el servidor los turnos comienzan desde 1.

## Ejecutar

En Linux o macOS:

```bash
chmod +x start.sh
./start.sh
```

Después abre `http://localhost:5000`. El script crea el entorno Python, instala dependencias, compila Angular e inicia el servidor.

## Desarrollo

Backend:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python backend/app.py
```

Frontend (servidor de desarrollo):

```bash
cd frontend
npm install
npm start
```

El frontend de desarrollo usa el proxy de Angular para acceder al backend en `localhost:5000`.

## Pruebas

```bash
backend/.venv/bin/pytest backend -q
cd frontend && npm test -- --watch=false
```

