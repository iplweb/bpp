FROM mpasternak79/docker-builder

# django live test server
EXPOSE 9015

# django debug (runserver)
EXPOSE 8080

RUN mkdir -p /usr/src/app

WORKDIR /usr/src/app

ADD tox.ini
ADD Makefile . 
ADD setup.py . 
ADD *.rst ./
ADD Gruntfile.js . 
ADD package.json . 
ADD yarn.lock . 
ADD .docker/stellar.yaml . 
ADD .docker/pytest.ini .
ADD .docker/test_shell.sh . 

ADD requirements*.txt ./

ENTRYPOINT ["/usr/src/app/test_shell.sh"]
