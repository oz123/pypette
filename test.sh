echo "Hello Upload" > "test.txt"
curl -v -F "test.txt=@test.txt" http://localhost:8000/upload
