# -*- coding:utf-8 -*-

import os
import re
import asyncio
import aiohttp
import aiofiles
import config
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
from pathlib import Path
import time

class Transform():
    def __init__(self):
        self.uc_path = ''
        self.mp3_path = ''
        self.id2file = {}  # {mp3 ID: file name}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36 QIHU 360SE",
            "Content-Type": "charset=utf-8"
            }
        self.cache_dic = {}
        self.step = 1

        
    def check_config(self):
        try:
            self.uc_path = eval(repr(config.UC_PATH).replace('\\\\', '/'))  #容错处理，替换正斜杠
            self.mp3_path = eval(repr(config.MP3_PATH).replace('\\\\', '/'))
            self.step = config.STEP_LENGTH
            self.max_attempts = int(config.AWAIT_TIME/3) + 1
        except Exception as e:
            print('Warning {} 请检查配置文件config.py'.format(str(e)))
            return False
        
        if self.step < 1:
            self.step = 1
        if not Path(self.uc_path).is_dir():
            print('缓存路径错误: {}'.format(self.uc_path))
            return False
        if not Path(self.mp3_path).is_dir():
            if not Path("./result/").is_dir():
                Path("./result/").mkdir() 
            self.mp3_path = "./result"
            print('目标路径错误: {} ，已在当前目录创建默认result文件夹'.format(self.mp3_path))

        # 容错处理 防止绝对路径结尾不是/
        if self.uc_path[-1] != '/':
            self.uc_path += '/'
        if self.mp3_path[-1] != '/':
            self.mp3_path += '/'
        return True

    
    def generate_files(self):
        files = os.listdir(self.uc_path)
        for file in files:
            if file[-3:] == '.uc':  # 后缀uc结尾为歌曲缓存
                song_id = self.get_song_by_file(file)
                if not song_id:
                    continue
                self.id2file[song_id] = self.uc_path + file
                
                
    def on_transform(self):
        start = time.time()
        # 按步长拆分原始字典
        list_key = self.id2file.keys()
        j = 0
        while j < len(list_key):
            for k in list(list_key)[j:j + self.step]:
                self.cache_dic[k] = self.id2file[k]
            loop = asyncio.get_event_loop()
            tasks = [self.do_transform(song_id, file) for song_id, file in self.cache_dic.items()]
            loop.run_until_complete(asyncio.wait(tasks))
            self.cache_dic.clear()
            j += self.step
        end = time.time()
        print('耗时：'+ str(end-start))
        print('共处理'+ str(len(self.id2file)) +'个文件')

        
    async def do_transform(self, song_id, uc_file):
        async with aiohttp.ClientSession() as session1: # session1向API请求歌曲信息
            song_name, singer_name, album, cover_url = await self.get_song_info(song_id, session1)
            await session1.close()
        async with aiofiles.open(uc_file, mode='rb') as f:
            uc_content = await f.read()
            mp3_content = bytearray()
            for byte in uc_content:
                byte ^= 0xa3
                mp3_content.append(byte)
          
            if song_name != song_id:    # 无法获取信息的用ID命名
                mp3_file_name = self.mp3_path + song_name + ' - ' + singer_name + '.mp3'
            else:
                mp3_file_name = self.mp3_path + song_name + '.mp3'
            async with aiofiles.open(mp3_file_name, 'wb') as mp3_file:
                await mp3_file.write(mp3_content)
                if song_name != song_id:
                    async with aiohttp.ClientSession() as session2: # session2从官方下载封面
                        await self.edit_mp3_info(mp3_file_name, song_name, singer_name, album, cover_url, session2)
                        await session2.close()
            print('success {}'.format(mp3_file_name))


    def get_song_by_file(self, file_name):
        match_inst = re.match('\d*', file_name)  # -前面的数字是歌曲ID，例：1347203552-320-0aa1
        if match_inst:
            return match_inst.group()

        
    async def get_song_info(self, song_id, session):
        attempts = status = 0
        song_name = singer = album = cover_url = ''
        jsons = []
        while attempts <= self.max_attempts:
            try:
                url = 'https://tenapi.cn/wyyinfo/?id={}'.format(song_id)
                async with session.get(url, headers=self.headers) as response:
                    status = response.status
                    jsons = await response.json(content_type="text/html")
            except Exception as e:  # 接收异常响应（页面无信息返回）
                print('响应：' + str(status) + "，调整单次文件个数后重试\n", Warning(str(e)))
                os._exit(1)
            song_name = jsons["data"]["songs"]
            singer = jsons["data"]["sings"]
            album = jsons["data"]["album"]
            cover_url= jsons["data"]["cover"]
            if song_name is None:   # 正常无信息返回时重试
                await asyncio.sleep(3)
                if attempts == self.max_attempts:   # 超时仍未获取信息
                    song_name = song_id
                    singer = album = cover_url = ''
                attempts += 1
            else:
                song_name = song_name.replace("/","&")  # 替换名称非法字符
                singer = singer.replace("/","&")
                break
        return song_name, singer, album, cover_url
    

    async def edit_mp3_info(self, file_name, song_name, singer_name, album, cover_url, session):
        pic_dir = Path("./pic/")
        if not pic_dir.is_dir():
            pic_dir.mkdir()  #检查pic目录
        pic_name = pic_dir / cover_url.split("/")[-1]

        # 开始写入id3
        id_info = ID3(file_name)
        id_info.add(TIT2(encoding=3, text=format(song_name)))
        id_info.add(TPE1(encoding=3, text=format(singer_name)))
        id_info.add(TALB(encoding=3, text=format(album)))
        # 检查pic文件是否存在
        attempts = 0
        while attempts < 2:
            if Path(pic_name).is_file() is False and attempts == 0:
                await self.get_cover_pic(pic_name, cover_url, session)
            else:
                pic = open(pic_name, "rb").read()
                id_info.add(APIC(encoding=3, mime='image/jpeg', type=3, data=pic))
            attempts += 1        
        id_info.save(v1=0, v2_version=3)

        
    async def get_cover_pic(self, pic_name, cover_url, session):
        try:
            async with session.get(cover_url, headers=self.headers) as response:
                cover_temp = await response.read()
                with open(pic_name, "wb") as f:
                    f.write(cover_temp)
        except Exception as e:
            print("无法获取封面图片\n", Warning(str(e)))
        
        
if __name__ == '__main__':
    transform = Transform()
    if not transform.check_config():
        exit()
    transform.generate_files()
    transform.on_transform()
