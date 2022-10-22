## 环境与依赖
+ python3.8.10
+ 依赖库：  
  + aiohttp==3.8.1
  + aiofiles==0.8.0 
  + mutagen==1.45.1
  + pathlib

## 使用方法
1. 编辑 config.py 对应的配置选项
1. 运行 transform.py <br>

> :warning: 特别注意 :warning: <br>
> 
> config.py 的 `STEP_LENGTH` 和 `AWAIT_TIME` 是根据 API 而设置的，可以根据实际使用的 API 进行调整 <br>
> 这里使用的 API 限制较多（每个 IP 在大约 45 秒内最多请求 50 首），默认的参数已通过测试 <br>
> 
**所以这里主要限制速度的是 API 的返回速度**

## 流程介绍:  
1. 对缓存文件的数据和 0xa3(163) 进行异或 (^) 运算，得出 mp3 文件
1. 根据歌曲 ID 去 [API](https://docs.tenapi.cn/wyyinfo.html) 获取歌曲信息
1. 将歌曲信息用 mutagen 写入 mp3 文件
1. 从官方地址获取专辑封面同时写入 mp3 文件
