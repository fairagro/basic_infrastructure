# To test the docker image locally #

```powershell
docker run -d -p 5000:5000 --restart=always --name registry registry:2
docker build -t localhost:5000/nextcloud-backup .
docker push localhost:5000/nextcloud-backup
kubectl run nextcloud-backup --rm -it --image localhost:5000/nextcloud-backup -- python /nextcloud-backup/main.py
```