#!/bin/bash

echo "🚀 Starting KnowinglyX AI OS..."

cd API

source .venv/bin/activate

uvicorn app.main:app --reload