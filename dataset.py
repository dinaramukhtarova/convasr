import os
import re
import csv
import gzip
import time
import math
import random
import subprocess
import numpy as np
import functools
import torch.utils.data
import scipy.io.wavfile
import librosa
import sentencepiece
import models
import transforms

class AudioTextDataset(torch.utils.data.Dataset):
	def __init__(self, source_paths, sample_rate, window_size, window_stride, window, num_input_features, labels, waveform_transform = None, feature_transform = None, max_duration = None, normalize_features = True, waveform_transform_debug_dir = None):
		self.window_stride = window_stride
		self.window_size = window_size
		self.sample_rate = sample_rate
		self.window = window
		self.num_input_features = num_input_features
		self.labels = labels
		self.waveform_transform = waveform_transform
		self.feature_transform = feature_transform
		self.normalize_features = normalize_features
		self.waveform_transform_debug_dir = waveform_transform_debug_dir

		self.ids = [list(sorted(((os.path.basename(data_or_path), row[0], row[1] if not row[1].endswith('.txt') else open(row[1]).read(), float(row[2]) if True and len(row) > 2 else -1) for row in csv.reader(gzip.open(data_or_path, 'rt') if data_or_path.endswith('.gz') else open(data_or_path), delimiter=',') if len(row) <= 2 or (max_duration is None or float(row[2]) < max_duration)), key = lambda t: t[-1])) for data_or_path in (source_paths if isinstance(source_paths, list) else [source_paths])]

	def __getitem__(self, index):
		for ids in self.ids:
			if index < len(ids):
				dataset_name, audio_path, reference, duration = ids[index]
				break
			else:
				index -= len(ids)

		signal, sample_rate = (audio_path, self.sample_rate) if isinstance(self.waveform_transform, transforms.SoxAug) else read_wav(audio_path, sample_rate = self.sample_rate)
		if self.waveform_transform is not None:
			signal, sample_rate = self.waveform_transform(signal, self.sample_rate, dataset_name = dataset_name)
		
		if self.waveform_transform_debug_dir:
			scipy.io.wavfile.write(os.path.join(self.waveform_transform_debug_dir, os.path.basename(audio_path)), self.sample_rate, signal.numpy())

		features = models.logfbank(signal, self.sample_rate, self.window_size, self.window_stride, self.window, self.num_input_features, normalize = self.normalize_features)
		if self.feature_transform is not None:
			features, sample_rate = self.feature_transform(features, self.sample_rate, dataset_name = dataset_name)

		reference_normalized = self.labels[0].encode(reference)[0]
		targets = [labels.encode(reference)[1] for labels in self.labels]
		return [dataset_name, audio_path, reference_normalized, features] + targets

	def __len__(self):
		return sum(map(len, self.ids))

class BucketingSampler(torch.utils.data.Sampler):
	def __init__(self, dataset, batch_size = 1, mixing = None):
		super().__init__(dataset)
		self.dataset = dataset
		self.batch_size = batch_size
		self.mixing = mixing or ([1 / len(self.dataset.ids)] * len(self.dataset.ids))
		self.shuffle(epoch = 0)

	def __iter__(self):
		for batch in self.shuffled[self.batch_idx:]:
			yield batch
			self.batch_idx += 1

	def __len__(self):
		return len(self.shuffled)

	def shuffle(self, epoch, batch_idx = 0):
		self.epoch = epoch
		self.batch_idx = batch_idx
		generator = torch.Generator()
		generator.manual_seed(self.epoch)

		mixing = [int(m * self.batch_size) for m in self.mixing]
		chunk = lambda xs, chunks: [xs[i * batch_size : (1 + i) * batch_size] for batch_size in [ len(xs) // chunks ] for i in range(chunks)]
		num_batches = int(len(self.dataset.ids[0]) // self.batch_size + 0.5)
		inds = [chunk(i, num_batches) for k, subset in enumerate(self.dataset.ids) for i in [sum(map(len, self.dataset.ids[:k])) + torch.arange(len(subset))]]
		batches = [torch.cat([i[torch.randperm(len(i), generator = generator)[:m]] for i, m in zip(t, mixing)]).tolist() for t in zip(*inds)]
		self.shuffled = [batches[k] for k in torch.randperm(len(batches), generator = generator).tolist()]

	def state_dict(self):
		return dict(epoch = self.epoch, batch_idx = self.batch_idx, shuffled = self.shuffled)

	def load_state_dict(self, state_dict):
		self.epoch, self.batch_idx, self.shuffled = state_dict['epoch'], state_dict['batch_idx'], (state_dict.get('shuffled') or self.shuffled)

class Labels:
	blank = '|'
	space = ' '
	repeat = '2'
	word_start = '<'
	word_end = '>'

	def __init__(self, lang, bpe = None, name = ''):
		self.lang = lang
		self.name = name
		self.preprocess_text = lang.preprocess_text
		self.preprocess_word = lang.preprocess_word
		self.bpe = None
		if bpe:
			self.bpe = sentencepiece.SentencePieceProcessor()
			self.bpe.Load(bpe)
		self.alphabet = self.lang.LABELS.lower()# + self.lang.LABELS[:-1].upper()
		self.blank_idx = len(self) - 1
		self.space_idx = self.blank_idx - 1
		self.repeat_idx = self.blank_idx - 2
		self.word_start_idx = self.alphabet.index(self.word_start) if self.word_start in self.alphabet else -1
		self.word_end_idx = self.alphabet.index(self.word_end) if self.word_end in self.alphabet else -1

	def find_words(self, text):
		text = re.sub(r'([^\W\d]+)2', r'\1', text)
		text = self.preprocess_text(text)
		words = re.findall(r'-?\d+|-?\d+-\w+|\w+', text)
		return list(filter(bool, (''.join(c for c in self.preprocess_word(w) if c in self).strip() for w in words)))

	def normalize_text(self, text):
		return ';'.join(' '.join(self.find_words(part)).lower().strip() for part in text.split(';')) or '*' 
		#return ' '.join(f'{w[:-1]}{w[-1].upper()}' for w in self.find_words(text.lower())) or '*' 

	def encode(self, text):
		normalized = self.normalize_text(text)
		chars = normalized.split(';')[0]
		chr2idx = {l: i for i, l in enumerate(str(self))}
		return normalized, torch.IntTensor([chr2idx[c] if i == 0 or c != chars[i - 1] else self.repeat_idx for i, c in enumerate(chars)] if self.bpe is None else self.bpe.EncodeAsIds(chars))

	def decode(self, idx, blank = None, space = None, replace2 = True):
		i2s = lambda i: ''.join(self[int(idx)] if not replace2 or k == 0 or self[int(idx)] != self[int(i[k - 1])] else '' for k, idx in enumerate(i)).replace(self.blank, blank or self.blank).replace(self.space, space or self.space)
		return list(map(i2s, idx))

	def postprocess_transcript(self, text, phonetic_replace_groups = []):
		replaceblank = lambda s: s.replace(self.blank * 10, ' ').replace(self.blank, '')
		replace2 = lambda s: ''.join(c if i == 0 or c != self.repeat else s[i - 1] for i, c in enumerate(s))
		replace22 = lambda s: ''.join(c if i == 0 or c != s[i - 1] else '' for i, c in enumerate(s))
		replacestar = lambda s: s.replace('*', '')
		replacespace = lambda s, sentencepiece_space = '\u2581': s.replace(sentencepiece_space, ' ')
		replacecap = lambda s: ''.join(c + ' ' if c.isupper() else c for c in s)
		replacephonetic = lambda s: s.translate({ord(c) : g[0] for g in phonetic_replace_groups for c in g.lower()})
		replacepunkt = lambda s: s.replace(',', '').replace('.', '')

		return functools.reduce(lambda text, func: func(text), [replacepunkt, replacespace, replacecap, replaceblank, replace2, replace22, replacestar, replacephonetic, str.strip], text)

	def __getitem__(self, idx):
		return {self.blank_idx : self.blank, self.repeat_idx : self.repeat, self.space_idx : self.space}.get(idx) or (self.alphabet[idx] if self.bpe is None else self.bpe.IdToPiece(idx))

	def __len__(self):
		return len(self.alphabet if self.bpe is None else self.bpe) + len([self.repeat, self.space, self.blank])

	def __str__(self):
		return self.alphabet + ''.join([self.repeat, self.space, self.blank])
	
	def __contains__(self, chr):
		return chr.lower() in self.alphabet

def collate_fn(batch, pad_to = 128):
	dataset_name, audio_path, reference, sample_inputs, *sample_targets = batch[0]
	inputs_max_len, *targets_max_len = [(1 + max((b[k].shape[-1] if torch.is_tensor(b[k]) else len(b[k])) for b in batch) // pad_to) * pad_to for k in range(3, 4 + len(sample_targets))]
	targets_max_len = max(targets_max_len)
	input_ = sample_inputs.new_zeros(len(batch), *(sample_inputs.shape[:-1] + (inputs_max_len,)))
	targets_ = sample_targets[0].new_zeros(len(batch), len(sample_targets), targets_max_len)
	input_lengths_fraction_, target_length_ = torch.FloatTensor(len(batch)), torch.IntTensor(len(batch), len(sample_targets))	
	for k, (dataset_name, audio_path, reference, input, *targets) in enumerate(batch):
		input_lengths_fraction_[k] = input.shape[-1] / input_.shape[-1]
		input_[k, ..., :input.shape[-1]] = input
		for j, t in enumerate(targets):
			targets_[k, j, :t.shape[-1]] = t
			target_length_[k, j] = len(t)
	dataset_name_, audio_path_, reference_, *_ = zip(*batch)
	#input_: NCT, targets_: NLt, target_length_: NL, input_lengths_fraction_: N
	return dataset_name_, audio_path_, reference_, input_, input_lengths_fraction_, targets_, target_length_

def read_wav(audio_path, normalize = True, stereo = False, sample_rate = None, max_duration = None):
	if audio_path.endswith('.wav'):
		sample_rate_, signal = scipy.io.wavfile.read(audio_path)
	else:
		sample_rate_, signal = sample_rate, torch.from_numpy(np.frombuffer(subprocess.check_output(['sox', '-V0', audio_path, '-b', '16', '-e', 'signed', '--endian', 'little', '-r', str(sample_rate), '-c', '1', '-t', 'raw', '-']), dtype = np.int16))

	signal = (signal if stereo else signal.squeeze(1) if signal.shape[1] == 1 else signal.mean(1)) if len(signal.shape) > 1 else (signal if not stereo else signal[..., None])
	if max_duration is not None:
		signal = signal[:int(max_duration * sample_rate_), ...]

	signal = torch.as_tensor(signal).to(torch.float32)
	if normalize:
		signal = models.normalize_signal(signal, dim = 0)
	if sample_rate is not None and sample_rate_ != sample_rate:
		sample_rate_, signal = resample(signal, sample_rate_, sample_rate)

	return signal, sample_rate_

def resample(signal, sample_rate_, sample_rate):
	return sample_rate, torch.from_numpy(librosa.resample(signal.numpy(), sample_rate_, sample_rate))

def bpetrain(input_path, output_prefix, vocab_size, model_type, max_sentencepiece_length):
	sentencepiece.SentencePieceTrainer.Train(f'--input={input_path} --model_prefix={output_prefix} --vocab_size={vocab_size} --model_type={model_type}' + (f' --max_sentencepiece_length={max_sentencepiece_length}' if max_sentencepiece_length else ''))

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	subparsers = parser.add_subparsers()
	cmd = subparsers.add_parser('bpetrain')
	cmd.add_argument('--input-path', '-i', required = True)
	cmd.add_argument('--output-prefix', '-o', required = True)
	cmd.add_argument('--vocab-size', default = 5000, type = int)
	cmd.add_argument('--model-type', default = 'unigram', choices = ['unigram', 'bpe', 'char', 'word'])
	cmd.add_argument('--max-sentencepiece-length', type = int, default = None)
	cmd.set_defaults(func = bpetrain)
	
	args = vars(parser.parse_args())
	func = args.pop('func')
	func(**args)
