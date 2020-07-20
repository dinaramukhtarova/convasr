python3 train.py $@ \
  --githttp https://github.com/vadimkantorov/convasr/commit/%h \
  --verbose --lang ru \
  --model JasperNetBig \
  --train-batch-size 256 --val-batch-size 64 \
  --scheduler MultiStepLR --decay-milestones 100000 140000 \
  --lr 1e-2 \
  --optimizer NovoGrad \
  --checkpoint data/experiments/JasperNetBig_NovoGrad_lr1e-2_wd1e-3_bs256____radio_1800h_mixed_train/checkpoint_epoch05_iter0036110.pt \
  --train-data-path data/mixed_train.csv.json \
  --val-data-path data/clean_val.csv.json data/splits/radio_100h_val.csv.json data/mixed_val.csv.json kontur_calls_micro/kontur_calls_micro.csv.json kontur_calls_micro/kontur_calls_micro.0.csv.json kontur_calls_micro/kontur_calls_micro.1.csv.json data/splits/radio_100h_2-4.2sec_val.json echomsk6000/cut/cut_test.json domain_set/transcripts/16042020/valset_kfold_16042020.0_fold_0.csv.json domain_set/transcripts/16042020/valset_kfold_16042020.1_fold_0.csv.json \
  --analyze kontur_calls_micro.csv \
  --val-iteration-interval 5000 \
  --fp16 O2 \
  --experiment-name radio_1800h_mixed_train \
  --epochs 50 --exphtml= #\