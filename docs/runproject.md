.\.venv\Scripts\Activate.ps1

python main.py or uvicorn main:app --reload

celery -A celery_queue.celery_app worker --loglevel=info --pool=solo

celery -A celery_queue.celery_app flower --port=5555

http://localhost:5555
