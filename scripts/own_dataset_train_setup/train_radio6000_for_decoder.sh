python3 train.py $@ \
  --githttp https://github.com/vadimkantorov/convasr/commit/%h \
  --verbose --lang ru \
  --model JasperNetBig \
  --train-batch-size 1664 --val-batch-size 512 \
  --scheduler MultiStepLR --decay-milestones 15000 20000 \
  --lr 1e-2 \
  --optimizer NovoGrad \
  --train-data-path echomsk6000/cut2/cut2_train.json \
  --checkpoint data/experiments/JasperNetBig_NovoGrad_lr2e-2_wd1e-3_bs1664____radio_1200h/checkpoint_epoch21_iter0015099.pt \
  --val-data-path data/clean_val.csv.json data/mixed_val.csv.json kontur_calls_micro/kontur_calls_micro.csv.json kontur_calls_micro/kontur_calls_micro.0.csv.json kontur_calls_micro/kontur_calls_micro.1.csv.json echomsk6000/cut2/cut2_microval.json \
  --analyze kontur_calls_micro.csv \
  --val-iteration-interval 5000 \
  --fp16 O2 \
  --experiment-name radio_1200h \
  --epochs 50 --exphtml= #\