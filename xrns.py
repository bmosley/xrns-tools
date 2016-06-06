#!/usr/bin/env python3
# needs flac and sox executables at your shell
import os
from xml.dom import minidom
from subprocess import call
from struct import pack
from wave import Wave_write, open as waveopen
from argh import ArghParser
from shutil import copy, rmtree
from zipfile import ZipFile

TEMP_SMPL_NAME_FORMAT = "./rnstmp/SampleData/Instrument{:02d} ({})/Sample{:02d} ({}).wav.16bit.wav"
DEST_SMPL_NAME_FORMAT = "./waves/I{:02d}-{}_S{:02d}-{}_{}-{}.wav"


class WaveWriter(Wave_write):

    def set_loop(self, start, end):
        self.loop_start = int(start)
        self.loop_end = int(end)

    def _write_header(self, initlength):
        assert not self._headerwritten
        self._file.write(b'RIFF')
        if not self._nframes:
            self._nframes = initlength // (self._nchannels * self._sampwidth)
        self._datalength = self._nframes * self._nchannels * self._sampwidth
        try:
            self._form_length_pos = self._file.tell()
        except (AttributeError, OSError):
            self._form_length_pos = None
        headers_length = 36
        if hasattr(self, "loop_start") and hasattr(self, "loop_end"):
            headers_length = 104
        self._file.write(pack('<L4s4sLHHLLHH4s',
            headers_length + self._datalength, b'WAVE', b'fmt ', 16,
            0x0001, self._nchannels, self._framerate,
            self._nchannels * self._framerate * self._sampwidth,
            self._nchannels * self._sampwidth,
            self._sampwidth * 8, b'data'))
        if self._form_length_pos is not None:
            self._data_length_pos = self._file.tell()
        self._file.write(pack('<L', self._datalength))
        self._headerwritten = True

    def add_sampler_loop_chunk(self):
        chunk = pack('<4sllllllllllllllll',
                    bytes('smpl', 'utf8'),  # chunk id, 4 bytes
                    60,  # chunk size
                    0,  # manufacturer,
                    0,  # product
                    0,  # sample period
                    60,  # midi unity note
                    0,  # midi pitch fraction
                    0,  # smpte format
                    0,  # smpte offset
                    1,  # number of sample loops
                    24,  # sampler data size
                    0,  # identifier
                    0,  # type (0=forward, 1=ping-pong, 2=backward)
                    self.loop_start,  # start
                    self.loop_end,  # end (warning: this sample is played)
                    0,  # fraction
                    0,  # play count. 0 means infinite
                    )
        self._file.write(chunk)


def get_instruments(song_xml_file):
    xml = minidom.parse(song_xml_file)
    for instrument in xml.getElementsByTagName("Instrument"):
        instrument_data = {"samples": [], "name": ""}
        for node in instrument.childNodes:
            if node.localName == "Name":
                instrument_data["name"] = node.firstChild.nodeValue
        for sample in instrument.getElementsByTagName("Sample"):
            sample_data = {}
            for node in sample.childNodes:
                if node.localName == "Name":
                    sample_data["name"] = node.firstChild.nodeValue
                if node.localName == "LoopMode":
                    sample_data["loop"] = node.firstChild.nodeValue
                if node.localName == "LoopStart":
                    sample_data["start"] = node.firstChild.nodeValue
                if node.localName == "LoopEnd":
                    sample_data["end"] = node.firstChild.nodeValue
            instrument_data["samples"].append(sample_data)
        yield instrument_data


def convert_wave(source_file, destination_file, start, end):
    source_wave = waveopen(source_file, 'r')
    destination_wave = WaveWriter(destination_file)
    destination_wave.setnchannels(source_wave.getnchannels())
    destination_wave.setsampwidth(source_wave.getsampwidth())
    destination_wave.setframerate(source_wave.getframerate())
    destination_wave.setnframes(source_wave.getnframes())
    destination_wave.set_loop(int(start), int(end))
    destination_wave.writeframes(source_wave.readframes(source_wave.getnframes()))
    destination_wave.add_sampler_loop_chunk()
    destination_wave.close()
    source_wave.close()


def sanitize_filename(file_name):
    """
    todo: actual implementation
    """
    return file_name.replace(":", "_")


def get_sampler_loop_chunk(start, end):
    return pack('<4sllllllllllllllll',
                bytes('smpl', 'utf8'),  # chunk id, 4 bytes
                60,  # chunk size
                0,  # manufacturer,
                0,  # product
                60,  # sample period
                0,  # midi unity note
                0,  # midi pitch fraction
                0,  # smpte format
                0,  # smpte offset
                1,  # number of sample loops
                24,  # sampler data size
                0,  # identifier
                0,  # type (0=forward, 1=ping-pong, 2=backward)
                int(start),  # start
                int(end),  # end (warning: this sample is played)
                0,  # fraction
                0,  # play count. 0 means infinite
                )


def unzip_xrns(xrns_filepath):
    with ZipFile(xrns_filepath) as zip:
        zip.extractall("./rnstmp")
    call(["find", "./rnstmp", "-name", "*.flac", "-exec", "flac", "-df", "{}", ";"], stdout=open(os.devnull, 'wb'),
         stderr=open(os.devnull, 'wb'))
    # python only opens 16 bit wavs so we force conversion upfront
    call(["find", "./rnstmp", "-name", "*.wav", "-exec", "sox", "{}", "-b", "16", "{}.16bit.wav", ";"],
         stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))


def cleanup():
    rmtree("./rnstmp")


def process_xrns(xrns_filepath):
    if not os.path.exists("./waves"):
        os.mkdir("./waves")
    unzip_xrns(xrns_filepath)
    instrument_index = 0
    for instrument in get_instruments("./rnstmp/Song.xml"):
        sample_index = 0
        for sample in instrument["samples"]:
            dest_wave_path = sanitize_filename(DEST_SMPL_NAME_FORMAT.format(
                    instrument_index,
                    instrument["name"],
                    sample_index,
                    sample["name"],
                    sample["start"] if sample["loop"] != "Off" else 0,
                    sample["end"] if sample["loop"] != "Off" else 0
            )).replace(' ', '_')
            source_wave_path = sanitize_filename(TEMP_SMPL_NAME_FORMAT.format(
                    instrument_index,
                    instrument["name"],
                    sample_index,
                    sample["name"]))
            if sample["loop"] != "Off":
                convert_wave(source_wave_path, dest_wave_path, sample["start"], sample["end"])
            else:
                copy(source_wave_path, dest_wave_path)
            sample_index += 1
        instrument_index += 1
    cleanup()


def extract(some_xrns_file_path):
    """
    Extract wavs from an xrns file to a "waves" dir:
    /waves/I01-InstrumentName_S01-SampleName_[loop start]-[loop end].wav
    """
    return process_xrns(some_xrns_file_path)

parser = ArghParser()
parser.add_commands([extract])
parser.dispatch()