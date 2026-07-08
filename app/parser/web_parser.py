import io
import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
import html2text
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from PIL import Image

from app.parser.base import ParserInterface

logger = logging.getLogger(__name__)


class WebParser(ParserInterface):
    """웹 페이지 콘텐츠를 파싱하여 마크다운으로 변환하는 파서"""
    
    def __init__(self):
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.body_width = 0  # 줄바꿈 비활성화
        self.h2t.single_line_break = True
        
    async def parsing(self, file_path: str, method: str = "default") -> List[Dict[str, Any]]:
        """
        웹 페이지를 파싱하여 마크다운으로 변환
        
        Args:
            file_path: 웹 페이지 URL
            method: 파싱 방법 (default)
            
        Returns:
            파싱된 콘텐츠 리스트
        """
        url = file_path
        logger.info(f"웹 페이지 파싱 시작: {url}")
        
        # URL 유효성 검증
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            raise ValueError(f"유효하지 않은 URL 형식: {url}")
        
        # 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp(prefix="web_parser_")
        
        try:
            # 웹 페이지 가져오기
            html_content = await self._fetch_url(url)
            
            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 메타데이터 추출
            metadata = self._extract_metadata(soup, url)
            
            # 불필요한 요소 제거
            self._clean_html(soup)
            
            # 메인 콘텐츠 추출
            main_content = self._extract_main_content(soup)
            
            # 이미지 처리
            images = await self._download_images(main_content, url, temp_dir)
            
            # 마크다운 변환
            markdown_text = self._convert_to_markdown(main_content)
            
            # 결과 생성
            result = {
                "page_number": 1,
                "text": markdown_text,
                "images": images,
                "temp_dir": temp_dir,
                "metadata": metadata
            }
            
            logger.info(f"웹 페이지 파싱 완료: {url}")
            return [result]
            
        except Exception as e:
            logger.error(f"웹 페이지 파싱 오류: {url}, {str(e)}")
            # 임시 디렉토리 정리
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise
    
    async def _fetch_url(self, url: str) -> str:
        """URL에서 HTML 콘텐츠 가져오기"""
        timeout = ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                
                # 인코딩 확인 및 텍스트 디코딩
                content_type = response.headers.get('content-type', '')
                if 'charset=' in content_type:
                    encoding = content_type.split('charset=')[-1].split(';')[0].strip()
                else:
                    encoding = 'utf-8'
                
                content = await response.read()
                return content.decode(encoding, errors='ignore')
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """HTML에서 메타데이터 추출"""
        metadata = {
            "url": url,
            "fetch_date": datetime.now().isoformat(),
            "title": "",
            "description": ""
        }
        
        # 타이틀 추출
        title_tag = soup.find('title')
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)
        
        # 메타 디스크립션 추출
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            metadata["description"] = meta_desc['content']
        
        # OG 태그 추출
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title and og_title.get('content') and not metadata["title"]:
            metadata["title"] = og_title['content']
            
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content') and not metadata["description"]:
            metadata["description"] = og_desc['content']
        
        return metadata
    
    def _clean_html(self, soup: BeautifulSoup):
        """불필요한 HTML 요소 제거"""
        # 제거할 태그들
        remove_tags = ['script', 'style', 'nav', 'header', 'footer', 'aside', 
                      'iframe', 'noscript', 'form', 'input', 'button']
        
        for tag in remove_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 광고 관련 클래스/ID 제거
        ad_patterns = ['ad', 'ads', 'advertisement', 'banner', 'popup', 'modal']
        for pattern in ad_patterns:
            # 클래스 기반 제거
            for element in soup.find_all(class_=lambda class_name: class_name and pattern in class_name.lower()):
                element.decompose()
            # ID 기반 제거
            for element in soup.find_all(id=lambda id_name: id_name and pattern in id_name.lower()):
                element.decompose()
    
    def _extract_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """메인 콘텐츠 영역 추출 - 범용적 접근"""
        # 1. 시맨틱 HTML5 태그 우선 확인
        semantic_tags = ['article', 'main', 'section']
        for tag in semantic_tags:
            elements = soup.find_all(tag)
            if elements:
                # 가장 긴 콘텐츠를 가진 요소 선택
                main_content = max(elements, key=lambda e: len(e.get_text(strip=True)))
                if len(main_content.get_text(strip=True)) > 100:  # 최소 텍스트 길이
                    return main_content
        
        # 2. role 속성 확인
        role_content = soup.find(attrs={'role': 'main'})
        if role_content and len(role_content.get_text(strip=True)) > 100:
            return role_content
        
        # 3. 일반적인 콘텐츠 컨테이너 패턴 (클래스/ID에서 키워드 검색)
        content_keywords = ['content', 'post', 'entry', 'article', 'main', 'body', 'text', 'story']
        
        # 모든 div 요소 검사
        all_divs = soup.find_all('div')
        candidate_divs = []
        
        for div in all_divs:
            # 클래스명 확인
            classes = div.get('class', [])
            class_str = ' '.join(classes) if isinstance(classes, list) else str(classes)
            
            # ID 확인
            div_id = div.get('id', '')
            
            # 키워드 매칭 점수 계산
            score = 0
            for keyword in content_keywords:
                if keyword in class_str.lower():
                    score += 2
                if keyword in div_id.lower():
                    score += 2
            
            # 텍스트 길이도 점수에 반영
            text_length = len(div.get_text(strip=True))
            if text_length > 100:
                score += 1
            if text_length > 500:
                score += 2
            if text_length > 1000:
                score += 3
                
            if score > 0:
                candidate_divs.append((div, score, text_length))
        
        # 점수와 텍스트 길이로 정렬하여 최적 후보 선택
        if candidate_divs:
            candidate_divs.sort(key=lambda candidate: (candidate[1], candidate[2]), reverse=True)
            return candidate_divs[0][0]
        
        # 4. 마지막 수단: 가장 긴 텍스트를 가진 요소
        if all_divs:
            main_content = max(all_divs, key=lambda d: len(d.get_text(strip=True)))
            if len(main_content.get_text(strip=True)) > 50:
                return main_content
        
        # 5. body 또는 전체 soup 반환
        body = soup.find('body')
        return body if body else soup
    
    async def _download_images(self, content: BeautifulSoup, base_url: str, temp_dir: str) -> List[Dict[str, Any]]:
        """이미지 처리 및 다운로드"""
        images = []
        img_tags = content.find_all('img')
        
        for idx, img in enumerate(img_tags):
            src = img.get('src', '')
            if not src:
                continue
                
            # 절대 URL로 변환
            img_url = urljoin(base_url, src)
            
            try:
                # 이미지 다운로드
                image_data = await self._download_image(img_url)
                if not image_data:
                    continue
                
                # 이미지 정보 추출
                img_info = self._extract_image_info(image_data, idx, img_url, temp_dir)
                if img_info:
                    img_info['alt'] = img.get('alt', '')
                    images.append(img_info)
                    
            except Exception as e:
                logger.warning(f"이미지 처리 오류: {img_url}, {str(e)}")
                continue
        
        return images
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """이미지 다운로드"""
        try:
            timeout = ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
        except Exception as e:
            logger.warning(f"이미지 다운로드 실패: {url}, {str(e)}")
        return None
    
    def _extract_image_info(self, image_data: bytes, idx: int, source_url: str, temp_dir: str) -> Optional[Dict[str, Any]]:
        """이미지 정보 추출 및 저장"""
        try:
            # 이미지 열기
            img = Image.open(io.BytesIO(image_data))
            
            # 파일명 생성
            ext = img.format.lower() if img.format else 'jpg'
            filename = f"web_img_{idx + 1}.{ext}"
            filepath = os.path.join(temp_dir, filename)
            
            # 이미지 저장
            img.save(filepath)
            
            return {
                "filename": filename,
                "path": filepath,
                "width": img.width,
                "height": img.height,
                "type": "web_image",
                "source_url": source_url,
                "note": "웹 페이지 이미지"
            }
        except Exception as e:
            logger.warning(f"이미지 정보 추출 실패: {str(e)}")
            return None
    
    def _convert_to_markdown(self, content: BeautifulSoup) -> str:
        """HTML을 마크다운으로 변환"""
        # BeautifulSoup 객체를 문자열로 변환
        html_str = str(content)
        
        # html2text로 변환
        markdown = self.h2t.handle(html_str)
        
        # 추가 정리
        # 연속된 빈 줄 제거
        lines = markdown.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            if line.strip():
                cleaned_lines.append(line)
                prev_empty = False
            elif not prev_empty:
                cleaned_lines.append(line)
                prev_empty = True
        
        return '\n'.join(cleaned_lines).strip()