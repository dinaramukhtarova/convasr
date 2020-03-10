set -e

CMD=$1
IN=$2
OUT=${3:-.}

EXT=${EXT:-mp3}
SUBLANG=${SUBLANG:-ru}
SUBEXT=srt
VERBOSE='--quiet --no-warnings'

youtube-dl () {
	wget --quiet --no-clobber https://yt-dl.org/downloads/latest/youtube-dl && chmod +x ./youtube-dl
	./youtube-dl $@
}

case $CMD in
	LIST)
		youtube-dl --get-id --flat-playlist "$IN"  | sed 's/^/http:\/\/youtu.be\//'
		;;

	RETR)
		mkdir -p "$OUT"
		BATCH=$([[ "$IN" != http* ]] && echo "--batch-file")
		AUDIOLIST=$(youtube-dl $VERBOSE --write-info-json --sub-lang $SUBLANG --write-sub --write-auto-sub --convert-subs $SUBEXT --extract-audio --audio-format $EXT --prefer-ffmpeg -o "$OUT/%(id)s.%(ext)s" $BATCH "$IN" --exec echo)

		for AUDIO in $AUDIOLIST; do
			JSON=${AUDIO//.$EXT/.info.json}
			SUB=${AUDIO//.$EXT/.$SUBLANG.$SUBEXT}
			
			echo $AUDIO
			if [ -f "$SUB" ]; then
				python3 -c "import sys, json, re; json.dump(dict(transcript = [dict(ref = ref, **{k : sum(howmany * sec for howmany, sec in zip(map(int, ts.replace(',', ':').split(':')), [60 * 60, 60, 1, 1e-3])) for k, ts in dict(begin = begin, end = end).items()}) for begin, end, ref in re.findall(r'(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)\s+(.+)', open(sys.argv[1]).read())], **json.load(open(sys.argv[2]))), open(sys.argv[3], 'w'), ensure_ascii = False, indent = 2, sort_keys = True)" "$SUB" "$JSON" "$AUDIO.json"
				rm "$JSON" "$SUB"
				echo $AUDIO.json
			fi
			ffprobe -hide_banner -i "$AUDIO"
		done
		;;
esac
