# Start from an official Python image — this is the base layer
# "3.11-slim" is a minimal version of Python 3.11 (no unnecessary extras)
FROM python:3.11-slim

# Set the working directory inside the container
# All subsequent commands run from this path
WORKDIR /app

# Copy only the dependency files first
# Why before copying the rest of the code?
# Docker builds in layers and caches each one.
# If you copy requirements first, Docker can reuse the dependency
# install layer on future builds — unless the dependencies change.
# This makes rebuilds much faster.
COPY pyproject.toml uv.lock ./

# Install uv, then use it to install dependencies
RUN pip install uv && uv sync --no-dev

# Now copy the rest of your application code
COPY . .

# Tell Docker that the container listens on port 8001
# This is documentation — it does not actually publish the port
EXPOSE 8001

# The command that runs when the container starts
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
