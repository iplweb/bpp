build:
	docker build -f ./Dockerfile-circleci-python-3.7-node-browsers-nginx-http-push -t mpasternak79/circleci-python:3.7-node-browsers-nginx-http-push  .
	docker build -f ./Dockerfile-db-psql12 -t mpasternak79/circleci-postgres:12 . 

push:
	docker push mpasternak79/circleci-python:3.7-node-browsers-nginx-http-push
	docker push mpasternak79/circleci-postgres:12
