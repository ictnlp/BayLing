python -m fastchat.serve.controller &

CUDA_VISIBLE_DEVICES=0 python model_worker.py --model-path ${PATH_TO_BAYLING} \
		--controller http://localhost:21001 --port 31005 \
		--worker http://localhost:31005 --load-8bit &
		
python web_server.py