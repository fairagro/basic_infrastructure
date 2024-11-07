# Use secure Wolfi base image (without Python installed)
FROM cgr.dev/chainguard/wolfi-base@sha256:8c36577d3901833243de49b7c85484e73bbf804597293fda3f28deab820e91d4 AS builder
# Set the version of Python to install
ARG python_version=3.12
# Do not cache the Python bytecode (aka don't create__pycache__ folders)
ENV PYTHONDONTWRITEBYTECODE=1
# Do not buffer stdout/stderr
ENV PYTHONUNBUFFERED=1
# Set the working directory in the container
WORKDIR /nextcloud-backup
# Install python and needed build tools
RUN apk add --no-cache python-${python_version}=3.12.7-r0 py${python_version}-pip=24.3.1-r0 python-${python_version}-dev=3.12.7-r0 build-base=1-r8
# Set the user to nonroot. It's defined in the Wolfi base image with the user id 65532
USER nonroot
# Copy the requirements.txt file to the container
COPY requirements.txt .
# Install the project dependencies
RUN pip install --no-cache-dir -r requirements.txt --user

# Actually we would like to use the Wolfi python image for the runtime as it contains even less software (e.g. no shell)
# and thus a smaller attack surface. Unfortunately the Wolfi project only features the current development versions of
# images for free.
FROM cgr.dev/chainguard/wolfi-base@sha256:8c36577d3901833243de49b7c85484e73bbf804597293fda3f28deab820e91d4
# python_version is out of scope now, so we need to redefine it
ARG python_version=3.12
# Set the working directory in the container
WORKDIR /nextcloud-backup
# copy python packages from builder stage
COPY --from=builder /home/nonroot/.local /home/nonroot/.local
# Install python
RUN apk add --no-cache python-${python_version}=3.12.7-r0 py${python_version}-setuptools=75.3.0-r0
# Set the user to nonroot. It's defined in the Wolfi base image with the user id 65532
USER nonroot
# Copy the application from host
COPY src/ /nextcloud-backup/
# We also copy the container-structure-test environment. This make it a lot easier to test the resulting container.
# COPY test/container-structure-test /middleware/test/container-structure-test
# Set the command to run when the container starts
CMD [ "/bin/sh" ]
