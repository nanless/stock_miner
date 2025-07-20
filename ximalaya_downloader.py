#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
喜马拉雅专辑音频下载器
支持下载指定专辑的所有音频文件

使用方法:
    python ximalaya_downloader.py <专辑ID或专辑URL>
    
示例:
    python ximalaya_downloader.py 12891461
    python ximalaya_downloader.py https://www.ximalaya.com/album/12891461
"""

import os
import re
import sys
import json
import time
import requests
import qrcode
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Optional
from io import BytesIO
import base64


class XimalayaDownloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.ximalaya.com/',
            'Origin': 'https://www.ximalaya.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.cookie_file = 'ximalaya_cookies.json'
        self.is_logged_in = False
        self.load_cookies()
        
    def load_cookies(self):
        """加载保存的cookies"""
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies_data = json.load(f)
                    for cookie in cookies_data:
                        self.session.cookies.set(**cookie)
                print("已加载保存的登录信息")
                self.is_logged_in = self.check_login_status()
                if self.is_logged_in:
                    print("登录状态有效")
                else:
                    print("登录状态已过期")
            except Exception as e:
                print(f"加载cookies失败: {e}")
    
    def save_cookies(self):
        """保存cookies到文件"""
        try:
            cookies_data = []
            for cookie in self.session.cookies:
                cookies_data.append({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path
                })
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies_data, f, ensure_ascii=False, indent=2)
            print("登录信息已保存")
        except Exception as e:
            print(f"保存cookies失败: {e}")
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            url = 'https://www.ximalaya.com/revision/main/getCurrentUser'
            response = self.session.get(url, timeout=10)
            data = response.json()
            if data.get('ret') == 200 and data.get('data', {}).get('isLogin'):
                user_info = data['data']
                print(f"当前登录用户: {user_info.get('nickname', '未知')}")
                return True
            return False
        except Exception as e:
            print(f"检查登录状态失败: {e}")
            return False
    
    def get_qr_login_info(self) -> Optional[Dict]:
        """获取二维码登录信息"""
        try:
            url = 'https://passport.ximalaya.com/web/qrCode/gen'
            params = {
                'level': 'L',
                'size': 256
            }
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            print(f"二维码API响应: {data}")
            
            # 检查不同的响应格式
            if data.get('ret') == 0 and 'data' in data:
                return data['data']
            elif 'qrId' in data and 'img' in data:
                # 直接返回包含qrId和img的数据
                return {
                    'qrId': data.get('qrId'),
                    'img': data.get('img')
                }
            else:
                print(f"获取二维码失败: {data.get('msg', '响应格式不正确')}")
                return None
        except Exception as e:
            print(f"获取二维码失败: {e}")
            return None
    
    def display_qr_code(self, qr_data: str):
        """显示二维码信息"""
        print(f"\n=== 二维码登录 ===")
        
        try:
            import base64
            import os
            
            # 直接处理base64数据（API返回的是纯base64字符串）
            image_data = base64.b64decode(qr_data)
            
            # 保存为临时文件
            qr_file = 'qr_code.png'
            with open(qr_file, 'wb') as f:
                f.write(image_data)
            
            print(f"二维码已保存为: {os.path.abspath(qr_file)}")
            print(f"请打开该图片文件查看二维码")
            
            # 尝试使用系统默认程序打开图片
            try:
                import subprocess
                import platform
                
                system = platform.system()
                if system == 'Darwin':  # macOS
                    subprocess.run(['open', qr_file])
                elif system == 'Windows':
                    subprocess.run(['start', qr_file], shell=True)
                elif system == 'Linux':
                    subprocess.run(['xdg-open', qr_file])
                print(f"已尝试自动打开二维码图片")
            except:
                print(f"无法自动打开图片，请手动打开: {os.path.abspath(qr_file)}")
                
        except Exception as e:
            print(f"处理二维码图片失败: {e}")
            print(f"原始数据长度: {len(qr_data)}")
            print(f"原始数据开头: {qr_data[:100]}...")
        
        print(f"\n然后使用喜马拉雅APP扫描二维码完成登录")
        print(f"等待扫码中...")
        print(f"==================\n")
    
    def check_qr_login_status(self, qr_id: str) -> str:
        """检查二维码登录状态
        返回值: 'success' - 登录成功, 'expired' - 二维码过期, 'cancelled' - 登录取消, 'waiting' - 等待中, 'error' - 错误
        """
        try:
            # 基于生成API路径 /web/qrCode/gen 推断可能的状态检查API
            urls_to_try = [
                # 与生成API相同路径结构，只是将gen改为其他动词
                'https://passport.ximalaya.com/web/qrCode/status',
                'https://passport.ximalaya.com/web/qrCode/query',
                'https://passport.ximalaya.com/web/qrCode/poll',
                'https://passport.ximalaya.com/web/qrCode/check',
                # 尝试简化路径
                'https://passport.ximalaya.com/qrCode/status',
                'https://passport.ximalaya.com/qrCode/check',
                # 尝试API路径
                'https://passport.ximalaya.com/api/qrCode/status',
                'https://passport.ximalaya.com/api/web/qrCode/status',
                # 尝试移动端
                'https://passport.ximalaya.com/mobile/qrCode/status',
                # 尝试v1/v2版本
                'https://passport.ximalaya.com/v1/web/qrCode/status',
                'https://passport.ximalaya.com/v2/web/qrCode/status'
            ]
            
            response = None
            for url in urls_to_try:
                try:
                    params = {'qrId': qr_id}
                    print(f"尝试API: {url}")
                    response = self.session.get(url, params=params, timeout=10)
                    
                    print(f"状态码: {response.status_code}")
                    
                    if response.status_code == 200:
                        # 检查响应内容是否为有效JSON
                        try:
                            test_json = response.json()
                            print(f"找到有效API端点: {url}")
                            print(f"响应内容: {response.text[:300]}...")
                            break
                        except ValueError:
                            print(f"响应不是JSON格式，尝试下一个...")
                            continue
                    elif response.status_code == 404:
                        print(f"端点不存在")
                        continue
                    else:
                        print(f"状态码: {response.status_code}")
                        continue
                        
                except Exception as e:
                    print(f"请求失败: {e}")
                    continue
            
            if not response or response.status_code != 200:
                print("所有API端点都无法访问，二维码登录功能暂时不可用")
                print("将跳过登录，尝试使用未登录状态下载")
                return 'skip'
                
            try:
                data = response.json()
                print(f"解析的JSON数据: {data}")
                
                # 检查不同的响应格式
                if data.get('ret') == 0 or data.get('code') == 0:
                    # 获取状态信息
                    status_data = data.get('data', data)
                    status = status_data.get('status', status_data.get('qrStatus', -1))
                    
                    print(f"登录状态: {status}")
                    
                    if status == 0:
                        return 'waiting'
                    elif status == 1:
                        print("已扫码，等待确认...")
                        return 'waiting'
                    elif status == 2:
                        print("登录成功!")
                        # 设置登录cookies
                        if 'web_login' in status_data:
                            login_url = status_data['web_login']
                            self.session.get(login_url, timeout=10)
                        elif 'loginUrl' in status_data:
                            login_url = status_data['loginUrl']
                            self.session.get(login_url, timeout=10)
                        self.save_cookies()
                        self.is_logged_in = True
                        return 'success'
                    elif status == 3:
                        print("二维码已过期")
                        return 'expired'
                    elif status == 4:
                        print("登录已取消")
                        return 'cancelled'
                    else:
                        print(f"未知状态: {status}")
                        return 'waiting'
                else:
                    print(f"API返回错误: ret={data.get('ret', data.get('code'))}, msg={data.get('msg', data.get('message', '未知错误'))}")
                    return 'error'
                    
            except ValueError as e:
                print(f"响应不是有效的JSON格式: {e}")
                print(f"原始响应: {response.text[:1000]}")
                return 'error'
                
        except Exception as e:
            print(f"检查登录状态失败: {e}")
            return 'error'
    
    def qr_login(self) -> bool:
        """二维码登录"""
        print("开始二维码登录...")
        qr_info = self.get_qr_login_info()
        if not qr_info:
            return False
        
        qr_id = qr_info['qrId']
        qr_data = qr_info['img']
        
        self.display_qr_code(qr_data)
        
        # 给用户足够时间打开二维码图片
        print("等待30秒，请在此期间打开二维码图片...")
        for i in range(30):
            time.sleep(1)
            print(f"\r剩余等待时间: {30-i}秒", end="", flush=True)
        print("\n开始检查登录状态...")
        
        # 轮询检查登录状态
        max_attempts = 200  # 最多等待200次，每次5秒，总共16.7分钟
        for attempt in range(max_attempts):
            time.sleep(5)
            status = self.check_qr_login_status(qr_id)
            
            if status == 'success':
                print("登录成功！")
                return True
            elif status == 'expired':
                print("二维码已过期，请重新获取")
                return False
            elif status == 'cancelled':
                print("登录已取消")
                return False
            elif status == 'skip':
                print("跳过登录，继续使用未登录状态")
                return False
            elif status == 'error':
                print("登录状态检查出错，请重试")
                return False
            elif status == 'waiting':
                remaining_time = (max_attempts - attempt - 1) * 5
                remaining_minutes = remaining_time // 60
                remaining_seconds = remaining_time % 60
                print(f"等待扫码中... ({attempt + 1}/{max_attempts}) - 剩余时间约 {remaining_minutes}分{remaining_seconds}秒")
        
        print("登录超时")
        return False
    
    def login_with_cookie(self, cookie_string: str) -> bool:
        """使用cookie字符串登录"""
        try:
            # 解析cookie字符串
            cookies = {}
            for item in cookie_string.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies[key] = value
            
            # 设置cookies
            for key, value in cookies.items():
                self.session.cookies.set(key, value, domain='.ximalaya.com')
            
            # 验证登录状态
            if self.check_login_status():
                self.save_cookies()
                self.is_logged_in = True
                print("Cookie登录成功")
                return True
            else:
                print("Cookie无效或已过期")
                return False
        except Exception as e:
            print(f"Cookie登录失败: {e}")
            return False
    
    def ensure_login(self) -> bool:
        """确保已登录"""
        if self.is_logged_in and self.check_login_status():
            return True
        
        print("需要登录才能访问完整功能")
        print("请选择登录方式:")
        print("1. 二维码登录")
        print("2. Cookie登录")
        print("3. 跳过登录（仅能下载部分免费内容）")
        
        choice = input("请输入选择 (1/2/3): ").strip()
        
        if choice == '1':
            return self.qr_login()
        elif choice == '2':
            cookie_string = input("请输入Cookie字符串: ").strip()
            return self.login_with_cookie(cookie_string)
        elif choice == '3':
            print("跳过登录，将尝试下载免费内容")
            return False
        else:
            print("无效选择")
            return False
        
    def extract_album_id(self, url_or_id: str) -> str:
        """
        从URL或直接输入中提取专辑ID
        """
        if url_or_id.isdigit():
            return url_or_id
            
        # 从URL中提取专辑ID
        patterns = [
            r'/album/(\d+)',
            r'albumId=(\d+)',
            r'id=(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
                
        raise ValueError(f"无法从 '{url_or_id}' 中提取专辑ID")
    
    def get_album_info(self, album_id: str) -> Dict:
        """
        获取专辑基本信息
        """
        url = f'https://www.ximalaya.com/revision/album?albumId={album_id}'
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('ret') != 200:
                raise Exception(f"获取专辑信息失败: {data.get('msg', '未知错误')}")
                
            album_data = data['data']
            # 安全获取作者信息
            author = '未知'
            if 'creatorsInfo' in album_data['mainInfo'] and album_data['mainInfo']['creatorsInfo']:
                author = album_data['mainInfo']['creatorsInfo'][0].get('nickname', '未知')
            elif 'albumUserInfo' in album_data['mainInfo']:
                author = album_data['mainInfo']['albumUserInfo'].get('nickname', '未知')
            
            return {
                'title': album_data['mainInfo']['albumTitle'],
                'author': author,
                'total_count': album_data['tracksInfo']['trackTotalCount'],
                'description': album_data['mainInfo'].get('detailRichIntro', '')
            }
        except Exception as e:
            raise Exception(f"获取专辑信息失败: {str(e)}")
    
    def get_track_list(self, album_id: str, page_num: int = 1, page_size: int = 30) -> List[Dict]:
        """
        获取专辑音频列表
        """
        url = f'https://www.ximalaya.com/revision/album/v1/getTracksList'
        params = {
            'albumId': album_id,
            'pageNum': page_num,
            'pageSize': page_size,
            'sort': 1  # 1: 正序, -1: 倒序
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            print(f"API响应状态: {data.get('ret')}, 消息: {data.get('msg', 'N/A')}")
            print(f"数据结构: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            if data.get('ret') != 200:
                # 尝试备用API
                return self._get_track_list_backup(album_id, page_num, page_size)
                
            tracks = []
            if 'data' in data:
                print(f"data字段内容: {list(data['data'].keys()) if isinstance(data['data'], dict) else 'Not a dict'}")
                if 'tracks' in data['data']:
                    print(f"找到tracks字段，包含 {len(data['data']['tracks'])} 个音频")
                    if len(data['data']['tracks']) == 0:
                        print("tracks为空，尝试备用API")
                        return self._get_track_list_backup(album_id, page_num, page_size)
                    for track in data['data']['tracks']:
                        tracks.append({
                            'track_id': track['trackId'],
                            'title': track['title'],
                            'index': track['index'],
                            'duration': track.get('duration', 0),
                            'is_free': track.get('isPaid', True) == False  # 免费音频
                        })
                else:
                    print("未找到tracks字段，尝试备用API")
                    return self._get_track_list_backup(album_id, page_num, page_size)
            
            return tracks
        except Exception as e:
            print(f"主API失败，尝试备用方法: {str(e)}")
            return self._get_track_list_backup(album_id, page_num, page_size)
    
    def _get_track_list_backup(self, album_id: str, page_num: int = 1, page_size: int = 30) -> List[Dict]:
        """
        备用的音频列表获取方法 - 使用Web API
        """
        url = f'https://www.ximalaya.com/revision/album/v1/getTracksList'
        params = {
            'albumId': album_id,
            'pageNum': page_num,
            'pageSize': page_size,
            'sort': 1
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            print(f"备用API响应状态: {data.get('ret')}, 消息: {data.get('msg', 'N/A')}")
            print(f"备用API数据结构: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            if data.get('ret') != 200:
                # 尝试第二个备用API
                return self._get_track_list_backup2(album_id, page_num, page_size)
                
            tracks = []
            if 'data' in data:
                print(f"备用API data字段内容: {list(data['data'].keys()) if isinstance(data['data'], dict) else 'Not a dict'}")
                if 'tracks' in data['data'] and data['data']['tracks']:
                    print(f"找到tracks字段，包含 {len(data['data']['tracks'])} 个音频")
                    for track in data['data']['tracks']:
                        tracks.append({
                            'track_id': track['trackId'],
                            'title': track['title'],
                            'index': track.get('index', track.get('orderNum', 1)),
                            'duration': track.get('duration', 0),
                            'is_free': track.get('isPaid', True) == False
                        })
                else:
                    print("备用API未找到tracks字段或为空，尝试第二个备用API")
                    return self._get_track_list_backup2(album_id, page_num, page_size)
            
            return tracks
        except Exception as e:
            print(f"第一个备用API失败: {str(e)}")
            return self._get_track_list_backup2(album_id, page_num, page_size)
    
    def _get_track_list_backup2(self, album_id: str, page_num: int = 1, page_size: int = 30) -> List[Dict]:
        """
        第二个备用的音频列表获取方法 - 使用移动端API
        """
        url = f'https://mobile.ximalaya.com/mobile/v1/album/track'
        params = {
            'albumId': album_id,
            'pageId': page_num,
            'pageSize': page_size,
            'sort': 1
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            print(f"第二备用API响应状态: {data.get('ret')}, 消息: {data.get('msg', 'N/A')}")
            
            tracks = []
            if data.get('ret') == 0 and 'data' in data and 'list' in data['data']:
                print(f"移动端API找到 {len(data['data']['list'])} 个音频")
                for track in data['data']['list']:
                    tracks.append({
                        'track_id': track['trackId'],
                        'title': track['title'],
                        'index': track.get('orderNum', track.get('index', 1)),
                        'duration': track.get('duration', 0),
                        'is_free': track.get('isPaid', True) == False
                    })
            else:
                print(f"移动端API数据结构: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                if 'data' in data:
                    print(f"移动端API data字段: {list(data['data'].keys()) if isinstance(data['data'], dict) else 'Not a dict'}")
            
            return tracks
        except Exception as e:
            print(f"移动端API失败: {str(e)}")
            return []
    
    def get_all_tracks(self, album_id: str) -> List[Dict]:
        """
        获取专辑所有音频
        """
        all_tracks = []
        page_num = 1
        page_size = 30
        
        while True:
            tracks = self.get_track_list(album_id, page_num, page_size)
            if not tracks:
                break
                
            all_tracks.extend(tracks)
            
            if len(tracks) < page_size:
                break
                
            page_num += 1
            time.sleep(0.5)  # 避免请求过快
            
        return all_tracks
    
    def get_audio_url(self, track_id: str) -> Optional[str]:
        """
        获取音频真实下载地址
        """
        # 尝试多个API端点
        apis = [
            # 经典的tracks API，从Chrome插件项目中发现
            f'https://www.ximalaya.com/tracks/{track_id}.json',
            f'http://www.ximalaya.com/tracks/{track_id}.json',
            # 其他备用API
            'https://www.ximalaya.com/revision/play/v1/audio',
            'https://mobile.ximalaya.com/mobile/v1/track/baseInfo',
            'https://www.ximalaya.com/revision/track/simple'
        ]
        
        for i, api_url in enumerate(apis):
            try:
                if i < 2:  # tracks API
                    response = self.session.get(api_url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    # 检查tracks API的响应格式
                    if 'play_path_64' in data:
                        return data['play_path_64']
                    elif 'play_path_32' in data:
                        return data['play_path_32']
                    elif 'play_path' in data:
                        return data['play_path']
                        
                elif i == 2:  # revision API
                    params = {'id': track_id, 'ptype': 1}
                    response = self.session.get(api_url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get('ret') == 200 and 'data' in data and 'src' in data['data']:
                        return data['data']['src']
                        
                elif i == 3:  # mobile API
                    params = {'trackId': track_id}
                    response = self.session.get(api_url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get('ret') == 0 and 'data' in data:
                        if 'playUrl' in data['data']:
                            return data['data']['playUrl']
                        elif 'src' in data['data']:
                            return data['data']['src']
                            
                elif i == 4:  # track simple API
                    params = {'trackId': track_id}
                    response = self.session.get(api_url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get('ret') == 200 and 'data' in data:
                        if 'playPath64' in data['data']:
                            return data['data']['playPath64']
                        elif 'src' in data['data']:
                            return data['data']['src']
                
                if i == 0:  # 只在第一个API失败时打印详细信息
                    print(f"API {i+1} 响应 (track_id: {track_id}): keys={list(data.keys()) if isinstance(data, dict) else 'Not dict'}")
                    
            except Exception as e:
                if i == 0:  # 只在第一个API失败时打印错误
                    print(f"获取音频地址异常 (track_id: {track_id}): {str(e)}")
                continue
        
        print(f"所有API都无法获取音频地址 (track_id: {track_id})")
        return None
    
    def download_audio(self, audio_url: str, file_path: str) -> bool:
        """
        下载音频文件
        """
        try:
            response = self.session.get(audio_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # 创建目录
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 下载文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True
        except Exception as e:
            print(f"下载失败: {str(e)}")
            return False
    
    def sanitize_filename(self, filename: str) -> str:
        """
        清理文件名中的非法字符
        """
        # 移除或替换非法字符
        illegal_chars = r'[<>:"/\\|?*]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 移除前后空格和点
        filename = filename.strip(' .')
        
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
            
        return filename
    
    def download_album(self, album_id: str, download_dir: str = './downloads', only_free: bool = True):
        """
        下载整个专辑
        """
        print(f"开始下载专辑 ID: {album_id}")
        
        # 获取专辑信息
        try:
            album_info = self.get_album_info(album_id)
            print(f"专辑名称: {album_info['title']}")
            print(f"作者: {album_info['author']}")
            print(f"总音频数: {album_info['total_count']}")
        except Exception as e:
            print(f"错误: {str(e)}")
            return
        
        # 创建下载目录
        safe_title = self.sanitize_filename(album_info['title'])
        album_dir = os.path.join(download_dir, safe_title)
        os.makedirs(album_dir, exist_ok=True)
        
        # 获取所有音频
        try:
            tracks = self.get_all_tracks(album_id)
            print(f"获取到 {len(tracks)} 个音频")
        except Exception as e:
            print(f"错误: {str(e)}")
            return
        
        # 过滤免费音频
        if only_free:
            free_tracks = [track for track in tracks if track['is_free']]
            print(f"其中免费音频: {len(free_tracks)} 个")
            tracks = free_tracks
        
        # 下载音频
        success_count = 0
        failed_count = 0
        
        for i, track in enumerate(tracks, 1):
            print(f"\n[{i}/{len(tracks)}] 正在处理: {track['title']}")
            
            # 获取音频下载地址
            audio_url = self.get_audio_url(str(track['track_id']))
            if not audio_url:
                print("  ❌ 获取下载地址失败")
                failed_count += 1
                continue
            
            # 构造文件名
            safe_title = self.sanitize_filename(track['title'])
            # 根据音频URL确定文件扩展名
            if '.m4a' in audio_url:
                ext = '.m4a'
            elif '.mp3' in audio_url:
                ext = '.mp3'
            else:
                ext = '.m4a'  # 默认扩展名
                
            filename = f"{track['index']:03d}_{safe_title}{ext}"
            file_path = os.path.join(album_dir, filename)
            
            # 检查文件是否已存在
            if os.path.exists(file_path):
                print("  ✅ 文件已存在，跳过")
                success_count += 1
                continue
            
            # 下载文件
            print(f"  📥 正在下载...")
            if self.download_audio(audio_url, file_path):
                print(f"  ✅ 下载成功")
                success_count += 1
            else:
                print(f"  ❌ 下载失败")
                failed_count += 1
            
            # 避免请求过快
            time.sleep(1)
        
        print(f"\n下载完成!")
        print(f"成功: {success_count} 个")
        print(f"失败: {failed_count} 个")
        print(f"下载目录: {album_dir}")


def main():
    if len(sys.argv) < 2:
        print("使用方法: python ximalaya_downloader.py <专辑ID或专辑URL> [选项]")
        print("示例:")
        print("  python ximalaya_downloader.py 12891461")
        print("  python ximalaya_downloader.py https://www.ximalaya.com/album/12891461")
        print("  python ximalaya_downloader.py --login https://www.ximalaya.com/album/12891461")
        print("选项:")
        print("  --login    强制重新登录")
        print("  --no-login 跳过登录检查")
        sys.exit(1)
    
    # 解析命令行参数
    force_login = '--login' in sys.argv
    no_login = '--no-login' in sys.argv
    
    # 找到专辑URL或ID（不是选项参数）
    url_or_id = None
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            url_or_id = arg
            break
    
    if not url_or_id:
        print("错误: 请提供专辑ID或专辑URL")
        sys.exit(1)
    
    downloader = XimalayaDownloader()
    
    # 登录检查
    if not no_login:
        if force_login or not downloader.is_logged_in:
            print("检查登录状态...")
            if force_login:
                # 强制登录时直接使用二维码登录
                print("强制登录模式，使用二维码登录...")
                downloader.qr_login()
            else:
                downloader.ensure_login()
    
    try:
        album_id = downloader.extract_album_id(url_or_id)
        downloader.download_album(album_id)
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()