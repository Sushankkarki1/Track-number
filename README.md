# Track Number

## Project Description

Track Number is a simple web-based vehicle registration lookup system. A user enters a vehicle registration number, the system validates the format, searches the PostgreSQL database, and displays vehicle details if the record exists.

This project uses sample data only. It does not connect to real government vehicle databases.

## Features

- Search vehicle details by registration number
- Validate registration number before database search
- Show clear invalid input and no-record-found messages
- Display vehicle name, model, owner, registered year, and color
- Password-protected admin page to add, update, and delete vehicles
- FastAPI automatic API documentation at `/docs` and `/redoc`

## Technology Stack

- Python
- FastAPI
- Uvicorn
- PostgreSQL
- SQLAlchemy
- psycopg2-binary
- HTML
- CSS
- Small vanilla JavaScript

## Project Structure

```text
Track-number/
|-- app/
|   |-- __init__.py
|   |-- main.py
|   |-- database.py
|   |-- models.py
|   |-- schemas.py
|   |-- crud.py
|   |-- auth.py
|   |-- routers/
|   |   |-- __init__.py
|   |   |-- search.py
|   |   `-- admin.py
|   `-- utils/
|       `-- logger/
|           `-- central_logger.py
|-- templates/
|   |-- index.html
|   |-- result.html
|   |-- admin_login.html
|   `-- admin.html
|-- static/
|   |-- css/
|   |   `-- style.css
|   `-- js/
|       `-- script.js
|-- .env.example
|-- .gitignore
|-- requirements.txt
|-- README.md
`-- main.py
```

## Database Setup

Create a PostgreSQL database named:

```sql
CREATE DATABASE track_number_db;
```

The application uses these tables:

- `owners`
- `vehicles`
- `admins`

When the app starts, SQLAlchemy creates missing tables safely. It does not drop the database, drop tables, or delete existing records. If the owner table is empty, it adds sample owners, vehicles, and one hashed admin password record for demonstration.

## Environment Variables

Copy `.env.example` to `.env` and update the password:

```env
DATABASE_URL=postgresql://postgres:*******@localhost:5432/track_number_db
ADMIN_SECRET_KEY=******
```

Do not commit your real `.env` file.

## Installation

Open PowerShell in this project folder:

```powershell
cd C:\Users\Sushank\Documents\XAVIER\Track-number
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Application

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:9000
```

## API Endpoints

- `GET /` - home search page
- `GET /result?registration_number=BA2PA1234` - HTML result page
- `GET /search/{registration_number}` - search API
- `GET /admin/login` - admin login page
- `POST /admin/login` - check admin password
- `GET /admin/logout` - logout admin
- `GET /admin` - password-protected admin page
- `GET /admin/vehicles` - list vehicles
- `POST /admin/vehicles` - add vehicle
- `PUT /admin/vehicles/{vehicle_id}` - update vehicle
- `DELETE /admin/vehicles/{vehicle_id}` - delete vehicle

API docs:

- `http://127.0.0.1:9000/docs`
- `http://127.0.0.1:9000/redoc`

## Sample Data

Owners:

- Sushank Karki, 9812345678, Kathmandu
- Ram Sharma, 9801111111, Pokhara

Vehicles:

- BA2PA1234, Hayabusa, model 2026, registered year 2021, Black
- BA1CHA5678, Royal Enfield Hunter 350, model 2024, registered year 2023, Red

Admin:

- username: admin
- password: admin123

The password is stored as a simple salted hash for academic demonstration.
The admin portal checks this password before allowing access to `/admin`.

## Testing

Try these inputs on the home page:

- `BA2PA1234` should show Sushank Karki
- `BA1CHA5678` should show Ram Sharma
- `BA9XYZ9999` should show no vehicle record found
- `abc` should show invalid registration number
- Empty input should show browser/form validation

Also open `/admin` and test adding, updating, and deleting a sample vehicle.
You should be redirected to `/admin/login` first.

## Future Improvements

- Add proper admin login
- Add audit records for admin changes
- Add stronger number plate validation rules
- Add pagination for many vehicle records
- Deploy online with HTTPS
