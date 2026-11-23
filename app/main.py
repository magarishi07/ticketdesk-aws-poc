import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import storage
from config import settings
from db import Base, SessionLocal, engine, get_db
from models import Attachment, Ticket, User, hash_password, verify_password

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
log = logging.getLogger('ticketdesk')

STATUSES = ['Open', 'In Progress', 'Resolved', 'Closed']
NEXT_STATUS = {'Open': 'In Progress', 'In Progress': 'Resolved', 'Resolved': 'Closed'}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # creates tables if missing
    with SessionLocal() as db:
        if settings.admin_password and not db.query(User).filter_by(username='admin').first():
            db.add(User(username='admin', password_hash=hash_password(settings.admin_password), role='admin'))
            db.commit()
            log.info('Seeded admin user')
    yield


app = FastAPI(title='TicketDesk', lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
templates = Jinja2Templates(directory='templates')
app.mount('/static', StaticFiles(directory='static'), name='static')

if not settings.s3_bucket:  # local mode: serve uploaded files from disk
    os.makedirs('uploads', exist_ok=True)
    app.mount('/files', StaticFiles(directory='uploads'), name='files')


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get('user_id')
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=303, headers={'Location': '/login'})
    return user


def get_ticket(db: Session, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail='Ticket not found')
    return ticket


def save_attachment(db: Session, ticket: Ticket, file: UploadFile):
    data = file.file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail='File larger than 5 MB')
    key = storage.save(ticket.id, file.filename, data, file.content_type)
    db.add(Attachment(ticket_id=ticket.id, filename=file.filename, storage_key=key))
    db.commit()
    log.info('Attachment %s saved for ticket %s', key, ticket.id)


@app.get('/health')
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'time': datetime.utcnow().isoformat()}


@app.get('/login')
def login_page(request: Request):
    return templates.TemplateResponse(request, 'login.html', {'error': None})


@app.post('/login')
def login(request: Request, username: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=username).first()
    if not user or not verify_password(password, user.password_hash):
        log.warning('Failed login for %s', username)
        return templates.TemplateResponse(request, 'login.html',
                                          {'error': 'Invalid username or password'}, status_code=401)
    request.session['user_id'] = user.id
    log.info('User %s logged in', username)
    return RedirectResponse('/', status_code=303)


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=303)


@app.get('/')
def dashboard(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    counts = dict(db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all())
    recent = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(5).all()
    return templates.TemplateResponse(request, 'dashboard.html',
                                      {'user': user, 'counts': counts, 'recent': recent, 'statuses': STATUSES})


@app.get('/tickets')
def list_tickets(request: Request, status: str | None = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Ticket).order_by(Ticket.created_at.desc())
    if status:
        q = q.filter(Ticket.status == status)
    return templates.TemplateResponse(request, 'tickets.html',
                                      {'user': user, 'tickets': q.all(), 'status': status, 'statuses': STATUSES})


@app.get('/tickets/new')
def new_ticket_page(request: Request, user: User = Depends(current_user)):
    return templates.TemplateResponse(request, 'new_ticket.html', {'user': user})


@app.post('/tickets')
def create_ticket(title: str = Form(...), description: str = Form(...), priority: str = Form('Medium'),
                  file: UploadFile | None = File(None),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    ticket = Ticket(title=title, description=description, priority=priority, created_by=user.id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    log.info('Ticket %s created by %s', ticket.id, user.username)
    if file and file.filename:
        save_attachment(db, ticket, file)
    return RedirectResponse(f'/tickets/{ticket.id}', status_code=303)


@app.get('/tickets/{ticket_id}')
def ticket_detail(ticket_id: int, request: Request,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    ticket = get_ticket(db, ticket_id)
    files = [(a, storage.url(a.storage_key)) for a in ticket.attachments]
    return templates.TemplateResponse(request, 'ticket_detail.html',
                                      {'user': user, 't': ticket, 'files': files,
                                       'next_status': NEXT_STATUS.get(ticket.status)})


@app.post('/tickets/{ticket_id}/status')
def advance_status(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ticket = get_ticket(db, ticket_id)
    nxt = NEXT_STATUS.get(ticket.status)
    if not nxt:
        raise HTTPException(status_code=400, detail='Ticket is already closed')
    log.info('Ticket %s: %s -> %s by %s', ticket.id, ticket.status, nxt, user.username)
    ticket.status = nxt
    ticket.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(f'/tickets/{ticket.id}', status_code=303)


@app.post('/tickets/{ticket_id}/attachments')
def add_attachment(ticket_id: int, file: UploadFile = File(...),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    save_attachment(db, get_ticket(db, ticket_id), file)
    return RedirectResponse(f'/tickets/{ticket_id}', status_code=303)
