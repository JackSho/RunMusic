# RunMusic

Every song is suitable for your running pace.

## Usage

    usage: [-h, --help]                     查看使用帮助
           [-l, --level <log_level>]        日志级别，缺省 INFO
           [-t, --threads <thread_num>]     线程数量，缺省 1 个线程
           [-i, --input <input_dir>]        输入目录，将扫描此目录里面的文件
           [-o, --output <output_dir>]      输出文件目录，缺省当前目录 .
           [-s, --step <step_per_min>]      目标声音节奏（步频），缺省 180
           [-v, --volume <number>]          目标声音音量增减，可取负数，缺省 0
           <file1> <file2> ...              要处理的多个声音文件
