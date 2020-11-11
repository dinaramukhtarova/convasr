import subprocess
import wave
import json
import torch
import numpy as np
import librosa
import soundfile
import scipy.io.wavfile

AUDIO_FILE_EXTENSIONS = {'.mp3', '.m4a', '.amr', '.gsm', '.wav', '.mp4', '.opus', '.ogg', '.webm', '.3gp'}

smax = torch.iinfo(torch.int16).max
f2s_numpy = lambda signal, max = np.float32(smax): np.multiply(signal, max).astype('int16')
s2f_numpy = lambda signal, max = np.float32(smax): np.divide(signal, max, dtype = 'float32')

def read_audio(
		audio_path,
		sample_rate,
		offset=0,
		duration=None,
		mono=True,
		raw_dtype='int16',
		dtype='float32',
		byte_order='little',
		backend=None,
		raw_bytes=None,
		raw_sample_rate=None,
		raw_num_channels=None,
):
	assert dtype in [None, 'int16', 'float32']
	assert backend in [None, 'scipy', 'soundfile', 'ffmpeg', 'sox']

	try:
		if audio_path is None or audio_path.endswith('.raw'):
			if audio_path is not None:
				with open(audio_path, 'rb') as f:
					raw_bytes = f.read()
			sample_rate_, signal = raw_sample_rate, np.frombuffer(raw_bytes, dtype = raw_dtype).reshape(-1, raw_num_channels)

		elif backend in ['scipy', None] and audio_path.endswith('.wav'):
			sample_rate_, signal = scipy.io.wavfile.read(audio_path)
			signal = signal[:, None] if len(signal.shape) == 1 else signal

		elif backend == 'soundfile':
			signal, sample_rate_ = soundfile.read(audio_path, dtype = raw_dtype)
			signal = signal[:, None] if len(signal.shape) == 1 else signal

		elif backend == 'sox':
			num_channels = int(subprocess.check_output(['soxi', '-V0', '-c', audio_path])) if not mono else 1
			params_fmt = ['-b', '16', '-e', 'signed'] if raw_dtype == 'int16' else ['-b', '32', '-e', 'float']
			params = [
				'sox',
				'-V0',
				audio_path
				] + params_fmt +[
				'--endian',
				byte_order,
				'-r',
				str(sample_rate),
				'-c',
				str(num_channels),
				'-t',
				'raw',
				'-'
			]
			sample_rate_, signal = sample_rate, np.frombuffer(subprocess.check_output(params), dtype = raw_dtype).reshape(-1, num_channels)
		elif backend in ['ffmpeg', None]:
			num_channels = int(
				subprocess.check_output([
					'ffprobe',
					'-i',
					audio_path,
					'-show_entries',
					'stream=channels',
					'-select_streams',
					'a:0',
					'-of',
					'compact=p=0:nk=1',
					'-v',
					'0'
				])
			) if not mono else 1
			params_fmt = ['-f', 's16le'] if raw_dtype == 'int16' else ['-f', 'f32le']
			params = [
				'ffmpeg',
				'-i',
				audio_path,
				'-nostdin',
				'-hide_banner',
				'-nostats',
				'-loglevel',
				'quiet'] + params_fmt + [
				'-ar',
				str(sample_rate),
				'-ac',
				str(num_channels),
				'-'
			]
			sample_rate_, signal = sample_rate, np.frombuffer(subprocess.check_output(params), dtype = raw_dtype).reshape(-1, num_channels)

	except:
		print(f'Error when reading [{audio_path}]')
		sample_rate_, signal = sample_rate, np.array([[]], dtype = dtype)

	if offset or duration is not None:
		signal = signal[
						slice(
							int(offset * sample_rate_) if offset else None,
							int((offset + duration) * sample_rate_) if duration is not None else None
						)]
	
	assert signal.dtype in [np.int16, np.float32]
	signal = signal.T
	
	if signal.dtype == np.int16 and dtype == 'float32':
		signal = s2f_numpy(signal)
	
	if mono and len(signal) > 1:
		assert signal.dtype == np.float32
		signal = signal.mean(0, keepdims = True)

	signal = torch.as_tensor(signal)

	if sample_rate is not None and sample_rate_ != sample_rate:
		signal, sample_rate_ = resample(signal, sample_rate_, sample_rate)

	return signal, sample_rate_


def write_audio(audio_path, signal, sample_rate, mono = False, backend = None, format = 'wav'):
	assert backend in [None, 'scipy', 'soundfile']
	assert signal.dtype == torch.float32 or len(signal) == 1 or (not mono)

	signal = signal if (not mono or len(signal) == 1) else signal.mean(dim = 0, keepdim = True)
	
	if backend == 'scipy' or (backend is None and (not audio_path or audio_path.endswith('.wav'))):
		assert signal.dtype == torch.float32
		scipy.io.wavfile.write(audio_path, sample_rate, f2s_numpy(signal.t().numpy()))
		return audio_path
	
	elif backend == 'soundfile':
		assert not isinstance(audio_path, str) or audio_path.endswith('.' + format)
		assert signal.dtype == torch.float32 or signal.dtype == torch.int16
		subtype = 'FLOAT' if signal.dtype == torch.float32 else 'PCM_16'
		soundfile.write(audio_path, signal.numpy(), endian = 'LITTLE', samplerate = sample_rate, subtype = subtype, format = format.upper()) 
		return audio_path


def resample(signal, sample_rate_, sample_rate):
	assert signal.dtype == torch.float32
	mono = len(signal) == 1
	if mono:
		signal = signal.squeeze(0)
	# librosa does not like mono 1T signals
	signal = torch.as_tensor(librosa.resample(signal.numpy(), sample_rate_, sample_rate))
	if mono:
		signal = signal.unsqueeze(0)
	return signal, sample_rate

def is_audio(audio_path):
	extension = audio_path.splitext()[-1].lower()
	return extension in AUDIO_FILE_EXTENSIONS

def compute_duration(audio_path, backend = None):
	assert backend in [None, 'scipy', 'ffmpeg', 'sox']

	if backend is None:
		if audio_path.endswith('.wav'):
			backend = 'scipy'
		else:
			backend = 'ffmpeg'

	if backend == 'scipy':
		signal, sample_rate = read_audio(audio_path, sample_rate = None, dtype = None, mono = False, backend = 'scipy')
		return signal.shape[-1] / sample_rate

	elif backend == 'ffmpeg':
		cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
			   'default=noprint_wrappers=1:nokey=1']
		return float(subprocess.check_output(cmd + [audio_path]))

	elif backend == 'sox':
		cmd = ['soxi', '-D']
		return float(subprocess.check_output(cmd + [audio_path]))

def extract_meta(audio_path, backend = None):
	'''
	Exctact metadata from audio:
		* num_channels
		* duration
	'''
	assert backend in [None, 'ffmpeg', 'wave']

	if backend is None:
		if audio_path.endswith('.wav'):
			backend = 'wave'
		else:
			backend = 'ffmpeg'

	if backend == 'ffmpeg':
		cmd = ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams']
		process_output = subprocess.check_output(cmd + [audio_path])
		try:
			ffprobe_data = json.loads(process_output)
			metadata = {
				'num_channels': ffprobe_data['streams'][0]['channels'],
				'duration'    : float(ffprobe_data['streams'][0]['duration'])
			}
		except:
			metadata = {
				'num_channels': 0,
				'duration'    : 0.0
			}
	elif backend == 'wave':
		with wave.open(audio_path, 'r') as w:
			nframes = w.getnframes()
			nchannels = w.getnchannels()
			duration = nframes / w.getframerate()
			metadata = {
				'num_channels': nchannels,
				'duration'    : duration
			}

	return metadata

if __name__ == '__main__':
	import argparse
	import time
	import utils

	parser = argparse.ArgumentParser()
	subparsers = parser.add_subparsers()
	cmd = subparsers.add_parser('timeit')

	cmd.add_argument('--audio-path', type=str, required=True)
	cmd.add_argument('--sample-rate', type=int, default=8000)
	cmd.add_argument('--mono', action='store_true')
	cmd.add_argument('--audio-backend', type=str, required=True)
	cmd.add_argument('--number', type=int, default=100)
	cmd.add_argument('--number-warmup', type=int, default=3)
	cmd.add_argument('--scale', type=int, default=1000)
	cmd.add_argument('--raw-dtype', default='int16', choices=['int16', 'float32'])
	cmd.add_argument('--dtype', default='float32', choices=['int16', 'float32'])
	cmd.set_defaults(func='timeit')

	args = parser.parse_args()

	if args.func == 'timeit':
		utils.reset_cpu_threads(1)
		for i in range(args.number_warmup):
			read_audio(args.audio_path, sample_rate=args.sample_rate, mono=args.mono, backend=args.audio_backend, dtype=args.dtype, raw_dtype=args.raw_dtype)

		start_process_time = time.process_time_ns()
		start_perf_counter = time.perf_counter_ns()
		for i in range(args.number):
			read_audio(args.audio_path, sample_rate=args.sample_rate, mono=args.mono, backend=args.audio_backend, dtype=args.dtype, raw_dtype=args.raw_dtype)
		end_process_time = time.process_time_ns()
		end_perf_counter = time.perf_counter_ns()
		process_time = (end_process_time - start_process_time) / args.scale / args.number
		perf_counter = (end_perf_counter - start_perf_counter) / args.scale / args.number
		print(f'|{args.audio_path:>20}|{args.number:>5}|{args.audio_backend:>10}|{process_time:9.0f}|{perf_counter:9.0f}|')
