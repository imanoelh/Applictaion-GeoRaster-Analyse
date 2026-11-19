L’erreur exacte est ici :

Error: Port 5183 is already in use
Ça veut dire : le frontend est déjà lancé sur 5183. Ce n’est pas une erreur du code.

## Actuellement :

Frontend 5183 : PID 13376
Backend 8010 : PID 31484
Si l’application marche déjà, ouvre simplement :

## Start-Process http://127.0.0.1:5183/map
Si tu veux relancer proprement le frontend, fais exactement :

taskkill /PID 13376 /F
Puis relance :

# cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRaster\GeoRaster\frontend"

# npm run dev -- --host 127.0.0.1 --port 5183 --strictPort --force
Pour vérifier GEE/backend :

# Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/gee/status
Si tu veux aussi relancer le backend proprement :

# taskkill /PID 31484 /F
Puis :

# cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRaster\GeoRaster\backend"

# $env:GEE_PROJECT_ID="gee-satellite-project-123456"
# $env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"

# C:\Users\Imane_C4E\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010

Important : ne lance pas deux fois le même frontend sur 5183. Si le port est déjà occupé, soit tu utilises l’application ouverte, soit tu arrêtes le PID avant de relancer.





lancement backend :
 cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRaster\GeoRaster\backend"

l'auhtentifictaion avec compte gee:
C:\Users\Imane_C4E\anaconda3\Scripts\earthengine.exe authenticate

$env:GEE_PROJECT_ID="gee-satellite-project-123456"
$env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"
C:\Users\Imane_C4E\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010

lancement frontend:
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRaster\GeoRaster\frontend"
>> 
>> npm run dev -- --host 127.0.0.1 --port 5183 --strictPort --force