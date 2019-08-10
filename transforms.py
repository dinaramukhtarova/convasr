import random
import torch
import dataset
import librosa
import pyrubberband

class SpeedPerturbation(object):
	def __init__(self, rate):
		self.rate = rate

	def __call__(self, signal, sample_rate):
		return torch.from_numpy(librosa.effects.time_stretch(signal.numpy(), fixed_or_uniform(self.rate))), sample_rate

class PitchShift(object):
	def __init__(self, n_steps):
		self.n_steps = n_steps

	def __call__(self, signal, sample_rate):
		return torch.from_numpy(pyrubberband.pyrb.pitch_shift(signal.numpy(), sample_rate, fixed_or_uniform(self.rate))), sample_rate
		#return torch.from_numpy(librosa.effects.pitch_shift(signal.numpy(), sample_rate, n_steps = noise_level)), sample_rate

class GainPerturbation(object):
	def __init__(self, gain_power):
		self.gain_power = gain_power

	def __call__(self, signal, sample_rate):
		return signal * (10. ** (fixed_or_uniform(self.gain_power) / 20.)), sample_rate

class AddWhiteNoise(object):
	def __init__(self, noise_level):
		self.noise_level = noise_level

	def __call__(self, signal, sample_rate):
		noise = torch.randn_like(signal).clamp(-1, 1)
		noise_level = fixed_or_uniform(self.noise_level)
		return signal + noise * noise_level, sample_rate

class MixExternalNoise(object):
	def __init__(self, noise_data_path, noise_level):
		self.noise_level = noise_level
		self.noise_paths = list(map(str.strip, open(noise_data_path))) if noise_data_path is not None else []

	def __call__(self, signal, sample_rate):
		noise_path = random.choice(self.noise_paths)
		noise_level = fixed_or_uniform(self.noise_level)
		noise, sample_rate = dataset.read_wav(noise_path, sample_rate = sample_rate, max_duration = 1.0 + len(signal) / sample_rate)
		noise = torch.cat([noise] * (1 + len(signal) // len(noise)))[:len(signal)]
		return signal + noise * noise_level, sample_rate

class SpecAugment(object):
	def __init__(self, n_freq_mask = 2, n_time_mask = 2, width_freq_mask = 6, width_time_mask = 6, replace_strategy = None):
		# fb code: https://github.com/facebookresearch/wav2letter/commit/04c3d80bf66fe749466cd427afbcc936fbdec5cd
		# width_freq_mask = 27, width_time_mask = 100, and n_freq_mask/n_time_mask = 2
		# google code: https://github.com/tensorflow/lingvo/blob/master/lingvo/core/spectrum_augmenter.py#L37-L42
		# width_freq_mask = 10 and width_time_mask = 50, and n_freq_mask/n_time_mask = 2

		self.replace_strategy = replace_strategy
		self.n_time_mask = n_time_mask
		self.n_freq_mask = n_freq_mask
		self.width_time_mask = width_time_mask
		self.width_freq_mask = width_freq_mask

	def __call__(self, spect):
		replace_val = spect.mean() if self.replace_strategy == 'mean' else 0

		for idx in range(self.n_freq_mask):
			f = random.randint(0, self.width_freq_mask)
			f0 = random.randint(0, spect.shape[0] - f)
			spect[f0:f0 + f, :] = replace_val

		for idx in range(self.n_time_mask):
			t = random.randint(0, min(self.width_time_mask, spect.shape[1]))
			t0 = random.randint(0, spect.shape[1] - t)
			spect[:, t0:t0 + t] = replace_val

		return spect

def fixed_or_uniform(r):
	return random.uniform(*r) if isinstance(r, list) else r
