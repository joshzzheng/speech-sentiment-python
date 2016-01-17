import pyaudio
import wave

from sys import byteorder
from array import array
from struct import pack

class Recorder:
    def __init__(self, audio_file_path):
        self.audio_file_path = audio_file_path
        self.threshold = 500
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        self.rate = 44100
        self.maximum = 16384

    def is_silent(self, snd_data):
        "Returns 'True' if below the 'silent' threshold"
        return max(snd_data) < self.threshold

    def normalize(self, snd_data):
        "Average the volume out"
        times = float(self.maximum)/max(abs(i) for i in snd_data)

        r = array('h')
        for i in snd_data:
            r.append(int(i*times))
        return r

    def trim(self, snd_data):
        "Trim the blank spots at the start and end"
        def _trim(snd_data):
            snd_started = False
            r = array('h')

            for i in snd_data:
                if not snd_started and abs(i)>self.threshold:
                    snd_started = True
                    r.append(i)

                elif snd_started:
                    r.append(i)
            return r

        # Trim to the left
        snd_data = _trim(snd_data)

        # Trim to the right
        snd_data.reverse()
        snd_data = _trim(snd_data)
        snd_data.reverse()
        return snd_data

    def add_silence(self, snd_data, seconds):
        "Add silence to the start and end of 'snd_data' of length 'seconds' (float)"
        r = array('h', [0 for i in range(int(seconds*self.rate))])
        r.extend(snd_data)
        r.extend([0 for i in range(int(seconds*self.rate))])
        return r

    def record(self):
        """
        Record a word or words from the microphone and 
        return the data as an array of signed shorts.

        Normalizes the audio, trims silence from the 
        start and end, and pads with 0.5 seconds of 
        blank sound to make sure VLC et al can play 
        it without getting chopped off.
        """
        p = pyaudio.PyAudio()
        stream = p.open(format=self.format, channels=1, rate=self.rate,
            input=True, output=True,
            frames_per_buffer=self.chunk_size)

        num_silent = 0
        snd_started = False

        r = array('h')

        while 1:
            # little endian, signed short
            snd_data = array('h', stream.read(self.chunk_size))
            if byteorder == 'big':
                snd_data.byteswap()
            r.extend(snd_data)

            silent = self.is_silent(snd_data)

            if silent and snd_started:
                num_silent += 1
            elif not silent and not snd_started:
                snd_started = True

            if snd_started and num_silent > 80:
                break

        sample_width = p.get_sample_size(self.format)
        stream.stop_stream()
        stream.close()
        p.terminate()

        r = self.normalize(r)
        r = self.trim(r)
        r = self.add_silence(r, 0.5)
        return sample_width, r

    def record_to_file(self):
        "Records from the microphone and outputs the resulting data to 'self.audio_file_path'"
        sample_width, data = self.record()
        data = pack('<' + ('h'*len(data)), *data)

        wf = wave.open(self.audio_file_path, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(self.rate)
        wf.writeframes(data)
        wf.close()
