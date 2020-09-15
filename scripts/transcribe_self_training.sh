set -e

CUDA_DEVICE=$1
THREAD=$2
echo $CUDA_DEVICE
echo $THREAD
export CUDA_VISIBLE_DEVICES=$CUDA_DEVICE

python3 transcribe.py \
	-i unsup_dataset/unsup_dataset_5k_$THREAD.json -o unsup_dataset_transcripts_1608_$THREAD \
         --mono --checkpoint data/experiments/JasperNetBig_NovoGrad_lr1e-4_wd1e-3_bs512____longtrain_finetune_before_self_train_bugfix/checkpoint_epoch478_iter0680000.pt \
         --txt --monofile --skip-json

#old data/experiments/JasperNetBig_NovoGrad_lr1e-4_wd1e-3_bs512____youtube_5000h_finetune_same_setup/checkpoint_epoch596_iter0555000.pt

