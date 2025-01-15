# Kubernetes with Python

This project demonstrates how to work with Kubernetes using Python.

## Prerequisites

- Python 3.12+
- pip (Python package installer)

## Installation

1. Create a virtual environment:

```bash
python3 -m venv venv
```

2. Activate the virtual environment:

```bash
source venv/bin/activate
```

3. Install the dependencies:

```bash
pip3 install -r requirements.txt
```

4. Run the application:

```bash
python -m uvicorn app.main:app --reload
```

The application will be available at `http://localhost:8000`

## API Documentation

Once the application is running, you can access:

- Interactive API documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative API documentation (ReDoc): `http://localhost:8000/redoc`


## Deactivating the Virtual Environment

When you're done working on the project, you can deactivate the virtual environment:

```bash
deactivate
```
