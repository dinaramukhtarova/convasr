CUDA_VISIBLE_DEVICES=0,1 python3 train.py $@ \
  --verbose --lang ru \
  --model Wav2LetterRu \
  --train-batch-size 80 --val-batch-size 80 \
  --lr 1e-2 --weight-decay 1e-3 \
  --scheduler MultiStepLR --decay-milestones 25000 50000 \
  --optimizer NovoGrad \
  --train-data-path data/mixed_train.csv \
  --val-data-path data/mixed_val.csv data/clean_val.csv ../sample_ok/sample_ok.convasr.csv \
  --val-iteration-interval 2500 \
  --train-waveform-transform AMRNB \
  --epochs 4

#CUDA_VISIBLE_DEVICES=0,1 python3 train.py $@ \
#  --verbose --lang ru --model Wav2LetterRu \
#  --train-batch-size 80 --val-batch-size 80 \
#  --lr 1e-4 \
#  --optimizer SGD \
#  --train-data-path data/mixed_train.csv \
#  --val-data-path ../sample_ok/sample_ok.convasr.csv \
#  --val-iteration-interval 2500 \
#  --checkpoint data/experiments/Wav2LetterRu_NovoGrad_lr1e-2_wd1e-3_bs80_augPSSPAMRNB0.5/checkpoint_epoch02_iter0074481.pt \
#  --train-feature-transform SpecAugment \
#  --epochs 5 --checkpoint-skip
