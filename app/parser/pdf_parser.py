import asyncio
import os
import shutil
import time
import logging
from collections import defaultdict
from pathlib import Path
from typing import List, Dict

import fitz
import nest_asyncio
import numpy as np
from dotenv import load_dotenv

from app.parser.base import ParserInterface

logger = logging.getLogger(__name__)

nest_asyncio.apply()
load_dotenv()


# PDF 파서 클래스
class PdfParser(ParserInterface):
    # 파서 생성자
    async def parsing(
        self, file_path: str, filename: str
    ) -> List[Dict]:
        """PDF 파일을 파싱하여 텍스트와 이미지를 추출합니다."""
        # OCR 필요 여부 먼저 확인
        needs_ocr = await self._check_ocr_required(file_path)
        if needs_ocr:
            return [{
                "needs_ocr": True,
                "message": "이 PDF는 스캔 이미지형 문서로 OCR 처리가 필요합니다."
            }]

        return await self._read_pymupdf(file_path, filename)

    @staticmethod
    def cleanup_temp_images(temp_dir: str) -> None:
        """임시 이미지 폴더 정리"""
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    @staticmethod
    def _find_chart_regions(drawings, min_elements: int = 5):
        """드로잉 요소들을 분석하여 차트 영역을 찾습니다."""

        if len(drawings) < min_elements:
            return []

        # 드로잉 요소들의 중심점과 크기 계산
        elements = []
        for drawing in drawings:
            rect = drawing.get("rect")
            if rect and rect.width > 1 and rect.height > 1:
                center_x = (rect.x0 + rect.x1) / 2
                center_y = (rect.y0 + rect.y1) / 2
                elements.append(
                    {
                        "rect": rect,
                        "center": (center_x, center_y),
                        "area": rect.width * rect.height,
                    }
                )

        if len(elements) < min_elements:
            return []

        # 영역별 클러스터링 (간단한 그리드 기반)
        clusters = defaultdict(list)
        grid_size = 100

        for elem in elements:
            grid_x = int(elem["center"][0] // grid_size)
            grid_y = int(elem["center"][1] // grid_size)
            clusters[(grid_x, grid_y)].append(elem)

        # 충분한 요소가 있는 클러스터만 차트로 간주
        chart_regions = []
        for cluster_elements in clusters.values():
            if len(cluster_elements) >= min_elements:
                min_x = min(e["rect"].x0 for e in cluster_elements)
                min_y = min(e["rect"].y0 for e in cluster_elements)
                max_x = max(e["rect"].x1 for e in cluster_elements)
                max_y = max(e["rect"].y1 for e in cluster_elements)

                width = max_x - min_x
                height = max_y - min_y
                if width > 50 and height > 50:
                    chart_regions.append(fitz.Rect(min_x, min_y, max_x, max_y))

        return chart_regions

    @staticmethod
    def _is_background_image(pix) -> bool:
        """이미지가 배경이나 로고 이미지인지 판단합니다."""
        samples = pix.samples
        if pix.n >= 3:
            height, width = pix.height, pix.width
            channels = pix.n

            img_array = np.frombuffer(samples, dtype=np.uint8)
            img_array = img_array.reshape(height, width, channels)
            rgb_array = img_array[:, :, :3]

            mean_color = rgb_array.mean(axis=(0, 1))
            color_std = rgb_array.std(axis=(0, 1))
            overall_std = color_std.mean()

            # 배경 이미지 판단 기준
            if all(c > 240 for c in mean_color):  # 흰색 배경
                return True
            if overall_std < 10:  # 단색 이미지
                return True

            color_diff = max(mean_color) - min(mean_color)
            if color_diff < 5:  # 회색조 이미지
                return True

        return False

    async def _check_ocr_required(self, file_path: str) -> bool:
        """PDF가 스캔 이미지형인지 텍스트 추출형인지 판단합니다.

        Returns:
            bool: OCR이 필요한 경우 True, 텍스트 추출 가능한 경우 False
        """
        return await asyncio.to_thread(self._check_ocr_required_sync, file_path)

    @staticmethod
    def _check_ocr_required_sync(file_path: str) -> bool:
        """PDF가 스캔 이미지형인지 동기적으로 확인합니다."""
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)

            # 빈 문서는 OCR 불필요
            if total_pages == 0:
                doc.close()
                return False

            # 샘플링할 페이지 수 결정 (최대 10페이지)
            sample_pages = min(total_pages, 10)
            pages_with_text = 0
            total_text_length = 0
            total_images = 0

            for i in range(sample_pages):
                page = doc[i]

                # 페이지에서 텍스트 추출
                text = page.get_text().strip()
                text_length = len(text)

                # 이미지 수 확인
                image_list = page.get_images(full=True)
                total_images += len(image_list)

                # 의미있는 텍스트가 있는지 확인 (최소 50자 이상)
                if text_length > 50:
                    pages_with_text += 1
                    total_text_length += text_length

            doc.close()

            # OCR 필요 여부 판단 기준
            # 1. 텍스트가 있는 페이지가 30% 미만
            text_page_ratio = pages_with_text / sample_pages
            if text_page_ratio < 0.3:
                logger.info(f"OCR 필요: 텍스트가 있는 페이지 비율이 {text_page_ratio:.1%}로 낮음")
                return True

            # 2. 페이지당 평균 텍스트가 100자 미만
            avg_text_per_page = total_text_length / sample_pages
            if avg_text_per_page < 100:
                logger.info(f"OCR 필요: 페이지당 평균 텍스트가 {avg_text_per_page:.0f}자로 적음")
                return True

            # 3. 이미지는 많지만 텍스트가 거의 없는 경우
            if total_images > sample_pages * 2 and avg_text_per_page < 200:
                logger.info(f"OCR 필요: 이미지 위주 문서 (이미지: {total_images}, 평균 텍스트: {avg_text_per_page:.0f}자)")
                return True

            logger.info(f"텍스트 추출 가능: 페이지 비율 {text_page_ratio:.1%}, 평균 텍스트 {avg_text_per_page:.0f}자")
            return False

        except Exception as e:
            logger.error(f"OCR 필요 여부 확인 중 오류: {e}")
            # 오류 발생 시 기본적으로 텍스트 추출 시도
            return False

    async def _read_pymupdf(
        self, file_path: str, filename: str
    ) -> List[Dict]:
        """PyMuPDF를 사용한 비동기 PDF 파싱"""
        return await asyncio.to_thread(self._pymupdf_sync, file_path, filename)

    @staticmethod
    def _table_to_markdown(table: List[List[str]]) -> str:
        """테이블을 마크다운 형식으로 변환"""
        if not table:
            return ""

        # 테이블 정규화
        normalized_table = []
        for row in table:
            new_row = []
            for cell in row:
                cell = cell if cell is not None else ""
                cell = cell.replace("\n", "<br>").strip()
                new_row.append(cell)
            normalized_table.append(new_row)

        # 빈 행 필터링
        filtered_table = []
        for row in normalized_table:
            filtered_row = [c.strip() for c in row if c.strip()]
            if filtered_row:
                filtered_table.append(filtered_row)

        if not filtered_table:
            return ""

        # 마크다운 형식으로 변환
        header = filtered_table[0]
        separator = ["---"] * len(header)

        lines = ["|" + "|".join(header) + "|", "|" + "|".join(separator) + "|"]

        for row in filtered_table[1:]:
            lines.append("|" + "|".join(row) + "|")

        return "\n".join(lines)

    @staticmethod
    def _create_temp_dir(filename: str) -> str:
        """임시 디렉토리를 생성합니다."""
        try:
            project_root = Path(__file__).parent.parent.parent
            temp_images_dir = project_root / "uploads" / "temp_images"
            temp_images_dir.mkdir(parents=True, exist_ok=True)

            pdf_name = Path(filename).stem
            timestamp = str(int(time.time() * 1000))
            temp_dir = temp_images_dir / f"{pdf_name}_{timestamp}"
            temp_dir.mkdir(exist_ok=True)

            return str(temp_dir)
        except Exception as e:
            logger.error(f"임시 디렉토리 생성 오류: {e}")
            raise

    @staticmethod
    def _extract_tables(page, table_bboxes: List) -> List[str]:
        """페이지에서 테이블을 추출합니다."""
        try:
            found_tables = page.find_tables()
            all_tables_md = []

            for table_obj in found_tables:
                table_rect = fitz.Rect(table_obj.bbox)
                # 중복 테이블 제거
                if any(
                    other.contains(table_rect) and other != table_rect
                    for other in table_bboxes
                ):
                    continue

                table_data = table_obj.extract()
                table_md = PdfParser._table_to_markdown(table_data)
                if table_md.strip():
                    all_tables_md.append(table_md)

            return all_tables_md
        except Exception as e:
            logger.error(f"테이블 추출 오류: {e}")
            return []

    @staticmethod
    def _extract_images(page, doc, temp_dir: str) -> List[Dict]:
        """페이지에서 이미지를 추출합니다."""
        try:
            images_info = []
            image_list = page.get_images(full=True)

            # 실제 렌더링되는 이미지 블록 찾기
            text_dict = page.get_text("dict")
            rendered_image_blocks = [
                block
                for block in text_dict.get("blocks", [])
                if block.get("type") == 1
            ]

            if not rendered_image_blocks:
                return images_info

            processed_count = 0
            for img in image_list:
                if processed_count >= len(rendered_image_blocks):
                    break

                xref = img[0]
                pix = fitz.Pixmap(doc, xref)

                # 크기 및 배경 필터링
                if (
                    pix.width < 100
                    or pix.height < 100
                    or PdfParser._is_background_image(pix)
                ):
                    pix = None
                    continue

                # 이미지 데이터 변환
                if pix.n - pix.alpha < 4:
                    img_data = pix.tobytes("png")
                else:
                    pix1 = fitz.Pixmap(fitz.csRGB, pix)
                    img_data = pix1.tobytes("png")
                    pix1 = None

                # 이미지 저장
                img_filename = f"page_{page.number + 1}_img_{xref}.png"
                img_path = os.path.join(temp_dir, img_filename)

                with open(img_path, "wb") as img_file:
                    img_file.write(img_data)

                images_info.append(
                    {
                        "filename": img_filename,
                        "path": img_path,
                        "width": pix.width,
                        "height": pix.height,
                        "type": "embedded_image",
                        "xref": xref,
                        "page": page.number + 1,
                    }
                )

                pix = None
                processed_count += 1

            return images_info
        except Exception as e:
            logger.error(f"이미지 추출 오류: {e}")
            return []

    @staticmethod
    def _extract_charts(page, temp_dir: str) -> List[Dict]:
        """페이지에서 차트를 추출합니다."""
        try:
            images_info = []
            drawings = page.get_drawings()

            if not drawings or len(drawings) <= 5:
                return images_info

            chart_regions = PdfParser._find_chart_regions(drawings)

            for chart_idx, region in enumerate(chart_regions):
                try:
                    # 차트 영역 검증
                    if region.x1 <= region.x0 or region.y1 <= region.y0:
                        logger.debug(f"잘못된 차트 영역 크기: {region}")
                        continue

                    # 차트 영역이 페이지 범위를 벗어나는지 확인
                    if region.x0 < 0 or region.y0 < 0 or region.x1 > page.rect.width or region.y1 > page.rect.height:
                        # 페이지 범위 내로 조정
                        region = fitz.Rect(
                            max(0, region.x0),
                            max(0, region.y0),
                            min(page.rect.width, region.x1),
                            min(page.rect.height, region.y1)
                        )

                    # 차트 영역 렌더링 - 안전한 설정 사용
                    mat = fitz.Matrix(1.0, 1.0)  # 확대 없이 원본 크기로
                    margin = 5
                    chart_rect = fitz.Rect(
                        max(0, region.x0 - margin),
                        max(0, region.y0 - margin),
                        min(page.rect.width, region.x1 + margin),
                        min(page.rect.height, region.y1 + margin),
                    )

                    # 최소 크기 확인
                    if chart_rect.width < 10 or chart_rect.height < 10:
                        continue

                    # 너무 큰 영역은 건너뛰기
                    if chart_rect.width > 2000 or chart_rect.height > 2000:
                        continue

                    pix = page.get_pixmap(matrix=mat, clip=chart_rect)
                    img_data = pix.tobytes("png")
                    img_filename = f"page_{page.number + 1}_chart_{chart_idx + 1}.png"
                    img_path = os.path.join(temp_dir, img_filename)

                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)

                    images_info.append(
                        {
                            "filename": img_filename,
                            "path": img_path,
                            "width": pix.width,
                            "height": pix.height,
                            "type": "chart",
                        }
                    )

                    pix = None

                except Exception as chart_error:
                    # bandwriter 오류는 조용히 건너뛰기
                    if "bandwriter" in str(chart_error).lower() or "code=4" in str(chart_error):
                        continue
                    # 다른 오류는 경고 로그
                    logger.warning(f"차트 추출 오류: {chart_error}")
                    continue

            return images_info
        except Exception as e:
            logger.error(f"차트 추출 중 전체 오류: {e}")
            return []

    @staticmethod
    def _extract_text(page, table_bboxes: List) -> str:
        """페이지에서 텍스트를 추출합니다."""
        try:
            blocks = page.get_text("blocks")
            page_text_list = []

            for block in blocks:
                block_rect = fitz.Rect(block[0], block[1], block[2], block[3])
                # 테이블 영역 제외
                if any(block_rect.intersects(tb) for tb in table_bboxes):
                    continue

                text = block[4].strip()
                if text and not text.isdigit():
                    page_text_list.append(text)

            return "\n".join(page_text_list)
        except Exception as e:
            logger.error(f"텍스트 추출 오류: {e}")
            return ""

    @staticmethod
    def _pymupdf_sync(file_path: str, filename: str) -> List[Dict]:
        """PyMuPDF를 사용하여 텍스트 및 이미지 추출 (동기)"""
        try:
            # PDF 문서 열기
            doc = fitz.open(file_path)
            result_list: List[Dict] = []

            # 임시 디렉토리 생성
            temp_dir = PdfParser._create_temp_dir(filename)

            for page in doc:
                # 테이블 경계 상자 추출
                found_tables = page.find_tables()
                table_bboxes = [fitz.Rect(table_obj.bbox) for table_obj in found_tables]

                # 1. 테이블 추출
                all_tables_md = PdfParser._extract_tables(page, table_bboxes)

                # 2. 이미지 추출
                images_info = PdfParser._extract_images(page, doc, temp_dir)

                # 3. 차트 추출
                chart_images = PdfParser._extract_charts(page, temp_dir)
                images_info.extend(chart_images)

                # 4. 텍스트 추출
                page_text = PdfParser._extract_text(page, table_bboxes)

                # 텍스트와 테이블 결합
                if all_tables_md:
                    page_text += "\n\n" + "\n\n".join(all_tables_md)

                result_list.append(
                    {
                        "page_number": page.number + 1,
                        "text": page_text,
                        "images": images_info,
                        "temp_dir": temp_dir,
                    }
                )

            doc.close()
            return result_list

        except Exception as e:
            logger.error(f"PDF 파싱 오류: {e}")
            raise