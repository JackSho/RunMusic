import getopt
import logging
import os
import sys
import tempfile
import time

import librosa
import numpy as np
import threadpool
from mutagen import id3, mp3
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s')
logger = logging.getLogger()


def new_bpm_rate(sound_bpm, bpm_target=180):
    target_mid = bpm_target / 2.0

    # 以目标节奏的 1.4 倍为分界点
    times = 1.4

    if sound_bpm < target_mid:
        return target_mid / sound_bpm
    elif sound_bpm >= target_mid and sound_bpm < target_mid * times:
        return target_mid / sound_bpm
    elif sound_bpm >= target_mid * times and sound_bpm < bpm_target:
        return bpm_target / sound_bpm
    else:
        return bpm_target / sound_bpm

    return 1.0


def sound_for_run(input_file,
                  step_per_min=180,
                  output_path=None,
                  volume=0,
                  output_ext='.mp3'):
    '''
    转换歌曲的节奏为指定步频的节奏
    :param input_path: 源文件路径
    :param output_path: 输出文件路径
    :param step_per_min: 输出文件节奏（步频）
    '''

    logger.debug('Input file is: %s' % input_file)
    logger.debug('Step per minute is: %d' % step_per_min)
    logger.info('Processing file: ' + input_file)

    # 识别音乐节奏
    logger.debug('Loading file: %s' % input_file)
    y, sr = librosa.load(input_file, sr=None, mono=False)
    y_mono = librosa.to_mono(y)
    tempo, beats = librosa.beat.beat_track(y=y_mono, sr=sr)
    logger.info('Recognized, input file BPM is: %f' % tempo)

    # 生成输出文件名
    source_path, source_filename = os.path.split(input_file)
    filename, ext = os.path.splitext(source_filename)
    if not output_path:
        output_path = source_path
    output_file = '%s/%s_%d_%d%s' % (output_path,
                                     filename, tempo, step_per_min, output_ext)
    logger.debug('Output file is: %s' % output_file)

    # 根据目标节奏，计算需要变换的比例
    rate = new_bpm_rate(tempo, step_per_min)
    logger.info('Stretch scale is: %f' % rate)

    # 对数据执行比例变换，双声道同时变换
    logger.debug('Stretching scale ...')
    new_y = np.array(
        [librosa.effects.time_stretch(y[0], rate),
         librosa.effects.time_stretch(y[1], rate)])

    # 生成新的 mp3 文件
    logger.debug('Creating new file: %s' % output_file)

    # 临时保存为 wav 文件
    temp = tempfile.NamedTemporaryFile()
    logger.debug('Exporting to temp wav file: %s' % temp.name)
    librosa.output.write_wav(temp.name, y=new_y, sr=sr)

    # 将 wav 转换成 mp3
    logger.debug('Converting from temp wav file to mp3')
    wav_source = AudioSegment.from_wav(temp.name)
    temp.close()

    logger.debug('Loaded wav file')

    # 转换之后的音乐声音会变小，这里增加 db
    if volume != 0:
        wav_source = wav_source + volume
        logger.info('Turn the volume up %d db' % volume)
    wav_source.export(output_file, format="mp3")
    logger.info('Created new mp3 file: %s' % output_file)

    # 复制源文件的 tag 信息到新 mp3 文件中
    logger.debug('Copying source tag')
    audio_src = mp3.MP3(input_file)
    audio_dst = id3.ID3(output_file)

    for k, v in audio_src.items():
        audio_dst[k] = v

    audio_dst.save()
    logger.debug('Wrote tag info to new file')
    logger.info('Processed file: %s' % input_file)

    return


usage_cmd = '''
usage: [-h, --help]                     查看使用帮助
       [-l, --level <log_level>]        日志级别，缺省 INFO
       [-t, --threads <thread_num>]     线程数量，缺省 1 个线程
       [-i, --input <input_dir>]        输入目录，将扫描此目录里面的文件
       [-o, --output <output_dir>]      输出文件目录，缺省当前目录 .
       [-s, --step <step_per_min>]      目标声音节奏（步频），缺省 180
       [-v, --volume <number>]          目标声音音量增减，可取负数，缺省 0
       <file1> <file2> ...              要处理的多个声音文件
'''


def usage(module, exit_code=None):
    print(usage_cmd)
    if exit_code is not None:
        sys.exit(exit_code)
    return


if __name__ == '__main__':

    if len(sys.argv) == 1:
        usage(sys.argv[0], 0)

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'hl:t:i:o:s:v:',
                                   ['help', 'level=', 'threads=', 'input=',
                                    'output=', 'step=', 'volume='])
    except getopt.GetoptError:
        logger.warning('Parse args error.')
        usage(sys.argv[0], 1)

    thread_num = 1  # 工作线程数据
    input_dir = None  # 输入目录
    output_dir = '.'  # 输出目录
    step_per_min = 180  # 目标步频
    volume = 0  # 音量增减变化
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage(sys.argv[0], 0)
        if opt in ('-l', '--level'):
            logger.setLevel(val)
        if opt in ('-t', '--threads'):
            thread_num = int(val)
        if opt in ('-i', '--input'):
            input_dir = val
        if opt in ('-o', '--output'):
            output_dir = val
        if opt in ('-s', '--step'):
            step_per_min = int(val)
        if opt in ('-v', '--volume'):
            volume = int(val)

    input_files = []  # 将要处理的文件列表

    if input_dir is not None:
        logger.debug('Input directory is: %s' % input_dir)
        if not os.path.isdir(input_dir):
            logger.warning('%s: No such file or directory' % input_dir)
            sys.exit(2)

        # 扫描输入目录的声音文件
        logger.debug('Scaning input directory')
        for file in os.listdir(input_dir):
            if file.endswith('.mp3'):
                input_files.append(os.path.join(input_dir, file))
        logger.info('Scan input directory, found %d sound files' %
                    len(input_files))

    logger.info('Input files are: %s' % args)

    for file in args:
        if not os.path.isfile(file):
            logger.warning('%s: No such file or directory' % file)
        if file.endswith('.mp3'):
            input_files.append(file)

    if len(input_files) == 0:
        logger.warning('None files should be update')
        sys.exit(0)
    else:
        logger.info('All %d files should be update' % len(input_files))

    logger.debug('Output directory is: %s' % output_dir)
    if not os.path.exists(output_dir):
        logger.debug('No such directory: %s' % output_dir)
        os.makedirs(output_dir)
        logger.warning('Created directory: %s' % output_dir)
    if not os.path.isdir(output_dir):
        logger.warning('%s: No such file or directory' % output_dir)
        sys.exit(3)

    logger.info('Step per minute is: %d' % step_per_min)

    thread_min = min(thread_num, len(input_files))
    pool = threadpool.ThreadPool(thread_min)
    logger.info('Created thread pool, contains %d worker threads' % thread_min)

    thread_args_list = []
    for file_name in input_files:
        thread_args_list.append(
            (None, {'input_file': file_name,
                    'step_per_min': step_per_min,
                    'output_path': output_dir,
                    'output_ext': '.mp3',
                    'volume': volume}))

    requests = threadpool.makeRequests(sound_for_run, thread_args_list)
    [pool.putRequest(req) for req in requests]

    logger.debug('Waiting all threads finish')
    time_start = time.time()
    pool.wait()
    logger.info('All threads stoped, application will stop')
    time_end = time.time()
    logger.info('Totally cost %f seconds' % (time_end - time_start))
