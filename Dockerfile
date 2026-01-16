FROM fedora:42

WORKDIR /work
RUN dnf install --assumeyes make gcc gcc-c++ \
            wget tar python3 python3-pip \
            tree emacs && \
    python3 -m pip install --no-cache-dir \
            setuptools wheel matplotlib jsonschema colorama && \
    dnf -y clean all

ENV PIN_ROOT=/opt/intel/pin
ENV PATH="/root/.local/bin:${PATH}"

ENTRYPOINT ["make"]

