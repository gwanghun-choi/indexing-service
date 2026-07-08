import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class ExcelTableChunker:
    """
    엑셀 테이블 전용 청킹 유틸리티
    헤더를 모든 청크에 고정으로 유지하고 행 단위 완전성을 보장
    """

    def __init__(self):
        pass

    def chunk_table_data(
        self,
        data: List[List[str]],
        sheet_name: str = "",
        chunk_size: int = 1000,
        format_type: str = "markdown",
    ) -> List[Dict]:
        """
        테이블 데이터를 헤더 고정 방식으로 청킹

        Args:
            data: 테이블 데이터 (전체 시트 데이터)
            sheet_name: 시트명
            chunk_size: 청크 크기
            format_type: 출력 형식 ("markdown" 또는 "structured")

        Returns:
            List[Dict]: 청크별 데이터 목록
        """
        try:
            logger.info(f"테이블 청킹 시작: {sheet_name}, 크기={chunk_size}")

            if not data or len(data) < 1:
                return self._create_empty_result(sheet_name)

            # ⭐ 핵심: 지능형 헤더 자동 감지
            header_row_idx, headers = self._detect_table_header(data)

            if header_row_idx == -1 or not headers:
                logger.warning("유효한 헤더를 찾을 수 없어 첫 번째 행을 헤더로 사용")
                header_row_idx = 0
                headers = self._extract_headers_from_row(data[0] if data else [])

            # 헤더 다음 행부터 데이터로 처리
            data_rows = (
                data[header_row_idx + 1 :] if header_row_idx + 1 < len(data) else []
            )

            logger.info(
                f"헤더 감지: 행 {header_row_idx + 1}, {len(headers)}개 컬럼, {len(data_rows)}개 데이터 행"
            )

            if not data_rows:
                return self._create_header_only_result(headers, sheet_name)

            # 청킹 방식에 따라 처리
            if format_type == "structured":
                return self._chunk_structured_text(
                    headers, data_rows, sheet_name, chunk_size
                )
            else:
                return self._chunk_markdown_table(
                    headers, data_rows, sheet_name, chunk_size
                )

        except Exception as e:
            logger.error(f"테이블 청킹 중 오류: {e}")
            return self._create_error_result(sheet_name, str(e))

    def _detect_table_header(self, data: List[List[str]]) -> Tuple[int, List[str]]:
        """
        지능형 헤더 자동 감지

        Returns:
            Tuple[int, List[str]]: (헤더 행 인덱스, 헤더 리스트)
        """
        try:
            if not data or len(data) < 2:
                return 0, self._extract_headers_from_row(data[0] if data else [])

            # 각 행의 데이터 품질 점수 계산
            row_scores = []
            for i, row in enumerate(data):
                score = self._calculate_row_score(row, i, data)
                row_scores.append((i, score, row))

            # 연속된 고품질 데이터 블록 찾기
            best_header_idx = self._find_best_header_position(row_scores, data)

            if best_header_idx >= 0 and best_header_idx < len(data):
                headers = self._extract_headers_from_row(data[best_header_idx])
                logger.info(f"헤더 감지 성공: 행 {best_header_idx + 1}")
                return best_header_idx, headers
            else:
                logger.warning("헤더 감지 실패, 첫 번째 행 사용")
                return 0, self._extract_headers_from_row(data[0])

        except Exception as e:
            logger.error(f"헤더 감지 중 오류: {e}")
            return 0, self._extract_headers_from_row(data[0] if data else [])

    def _calculate_row_score(
        self, row: List[str], row_idx: int, data: List[List[str]]
    ) -> float:
        """
        행의 데이터 품질 점수 계산 (0.0 ~ 1.0)
        """
        if not row:
            return 0.0

        score = 0.0
        factors = 0

        # 1. 데이터 밀도 (채워진 셀 비율)
        filled_cells = sum(1 for cell in row if cell and str(cell).strip())
        if len(row) > 0:
            density = filled_cells / len(row)
            score += density * 0.4
            factors += 0.4

        # 2. 텍스트 일관성 (헤더는 보통 모두 텍스트)
        if filled_cells > 0:
            text_ratio = (
                sum(
                    1
                    for cell in row
                    if cell and str(cell).strip() and not str(cell).isdigit()
                )
                / filled_cells
            )
            score += text_ratio * 0.2
            factors += 0.2

        # 3. 연속성 보너스 (다음 몇 행이 비슷한 구조인지)
        if row_idx + 1 < len(data) and row_idx + 3 < len(data):
            consistency = self._check_row_consistency(
                row, data[row_idx + 1 : row_idx + 4]
            )
            score += consistency * 0.3
            factors += 0.3

        # 4. 위치 보너스 (너무 마지막 행은 헤더일 가능성 낮음)
        position_bonus = max(0, (len(data) - row_idx - 5) / len(data)) * 0.1
        score += position_bonus
        factors += 0.1

        return score / factors if factors > 0 else 0.0

    def _check_row_consistency(
        self, header_row: List[str], next_rows: List[List[str]]
    ) -> float:
        """
        헤더 후 몇 행이 일관된 구조를 가지는지 확인
        """
        if not next_rows:
            return 0.0

        header_cols = len([cell for cell in header_row if cell and str(cell).strip()])
        if header_cols == 0:
            return 0.0

        consistency_scores = []
        for row in next_rows:
            if not row:
                consistency_scores.append(0.0)
                continue

            row_cols = len([cell for cell in row if cell and str(cell).strip()])
            # 컬럼 수 일치도
            col_match = (
                min(row_cols, header_cols) / max(row_cols, header_cols)
                if max(row_cols, header_cols) > 0
                else 0
            )
            consistency_scores.append(col_match)

        return (
            sum(consistency_scores) / len(consistency_scores)
            if consistency_scores
            else 0.0
        )

    def _find_best_header_position(
        self, row_scores: List[Tuple[int, float, List[str]]], data: List[List[str]]
    ) -> int:
        """
        최적의 헤더 위치 찾기
        """
        if not row_scores:
            return 0

        # 점수 기준으로 정렬
        sorted_scores = sorted(row_scores, key=lambda row_score: row_score[1], reverse=True)

        # 상위 후보들 중에서 연속된 데이터 블록을 가진 행 찾기
        for row_idx, score, row in sorted_scores[: min(5, len(sorted_scores))]:
            if score < 0.3:  # 최소 품질 기준
                continue

            # 이 행 다음에 최소 2행의 데이터가 있는지 확인
            if row_idx + 2 < len(data):
                next_rows_quality = self._check_row_consistency(
                    row, data[row_idx + 1 : row_idx + 4]
                )
                if next_rows_quality >= 0.5:  # 연속성 기준
                    return row_idx

        # 기준을 만족하는 행이 없으면 점수가 가장 높은 행 선택
        best_idx = sorted_scores[0][0] if sorted_scores else 0
        return best_idx

    def _extract_headers_from_row(self, row: List[str]) -> List[str]:
        """특정 행에서 헤더 추출 및 정리"""
        if not row:
            return []

        headers = []
        for i, cell in enumerate(row):
            if cell and str(cell).strip():
                # 특수 문자 정리
                cleaned = str(cell).strip().replace("|", "").replace("\n", " ")
                headers.append(cleaned)
            else:
                headers.append(f"컬럼{i+1}")

        return headers

    def _extract_headers(self, data: List[List[str]]) -> List[str]:
        """기존 메서드 - 호환성 유지용"""
        return self._extract_headers_from_row(data[0] if data else [])

    def _chunk_markdown_table(
        self,
        headers: List[str],
        data_rows: List[List[str]],
        sheet_name: str,
        chunk_size: int,
    ) -> List[Dict]:
        """마크다운 테이블을 헤더 고정 방식으로 청킹"""
        try:
            chunks = []

            # 헤더 부분 크기 계산 (고정 부분)
            header_line = "| " + " | ".join(headers) + " |"
            separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            base_header = f"# {sheet_name}\n\n{header_line}\n{separator_line}\n"

            header_size = len(base_header)

            # 헤더가 청크 크기를 초과하는 경우
            if header_size >= chunk_size:
                logger.warning(
                    f"헤더 크기({header_size})가 청크 크기({chunk_size})를 초과, 구조화된 텍스트로 변경"
                )
                return self._chunk_structured_text(
                    headers, data_rows, sheet_name, chunk_size
                )

            # 데이터 행들을 순차적으로 청킹
            current_rows = []
            current_size = header_size

            for row_idx, row in enumerate(data_rows):
                # 현재 행의 마크다운 크기 계산
                formatted_row = self._format_markdown_row(row, headers)
                row_size = len(formatted_row) + 1  # +1 for newline

                # 크기 초과 체크
                if current_size + row_size > chunk_size and current_rows:
                    # 현재 청크 완성
                    chunk_content = self._build_markdown_chunk(
                        headers, current_rows, sheet_name, len(chunks) + 1
                    )
                    chunks.append(
                        {
                            "page_number": len(chunks) + 1,
                            "chunk_index": len(chunks),
                            "text": chunk_content,
                            "row_count": len(current_rows),
                            "type": "markdown_table",
                        }
                    )

                    # 새 청크 시작
                    current_rows = []
                    current_size = header_size

                # 현재 행 추가
                current_rows.append(row)
                current_size += row_size

                # 단일 행도 청크 크기를 초과하는 경우 강제 추가
                if current_size > chunk_size and len(current_rows) == 1:
                    logger.warning(
                        f"단일 행이 청크 크기 초과, 강제 포함 (행 {row_idx + 1})"
                    )
                    chunk_content = self._build_markdown_chunk(
                        headers, current_rows, sheet_name, len(chunks) + 1
                    )
                    chunks.append(
                        {
                            "page_number": len(chunks) + 1,
                            "chunk_index": len(chunks),
                            "text": chunk_content,
                            "row_count": 1,
                            "type": "markdown_table",
                        }
                    )
                    current_rows = []
                    current_size = header_size

            # 마지막 남은 행들 처리
            if current_rows:
                chunk_content = self._build_markdown_chunk(
                    headers, current_rows, sheet_name, len(chunks) + 1
                )
                chunks.append(
                    {
                        "page_number": len(chunks) + 1,
                        "chunk_index": len(chunks),
                        "text": chunk_content,
                        "row_count": len(current_rows),
                        "type": "markdown_table",
                    }
                )

            logger.info(f"마크다운 테이블 청킹 완료: {len(chunks)}개 청크")
            return chunks

        except Exception as e:
            logger.error(f"마크다운 테이블 청킹 중 오류: {e}")
            return []

    def _chunk_structured_text(
        self,
        headers: List[str],
        data_rows: List[List[str]],
        sheet_name: str,
        chunk_size: int,
    ) -> List[Dict]:
        """구조화된 텍스트로 청킹"""
        try:
            chunks = []

            # 기본 헤더 크기 계산
            base_header = f"# {sheet_name}\n\n## 테이블 데이터\n\n"
            base_size = len(base_header)

            current_rows = []
            current_size = base_size

            for row_idx, row in enumerate(data_rows):
                # 현재 행의 구조화된 텍스트 크기 계산
                row_text = self._build_structured_row_text(
                    headers, row, len(current_rows) + 1
                )
                row_size = len(row_text) + 2  # +2 for extra newlines

                # 크기 초과 체크
                if current_size + row_size > chunk_size and current_rows:
                    # 현재 청크 완성
                    chunk_content = self._build_structured_chunk(
                        headers, current_rows, sheet_name, len(chunks) + 1
                    )
                    chunks.append(
                        {
                            "page_number": len(chunks) + 1,
                            "chunk_index": len(chunks),
                            "text": chunk_content,
                            "row_count": len(current_rows),
                            "type": "structured_text",
                        }
                    )

                    # 새 청크 시작
                    current_rows = []
                    current_size = base_size

                # 현재 행 추가
                current_rows.append(row)
                current_size += row_size

            # 마지막 남은 행들 처리
            if current_rows:
                chunk_content = self._build_structured_chunk(
                    headers, current_rows, sheet_name, len(chunks) + 1
                )
                chunks.append(
                    {
                        "page_number": len(chunks) + 1,
                        "chunk_index": len(chunks),
                        "text": chunk_content,
                        "row_count": len(current_rows),
                        "type": "structured_text",
                    }
                )

            logger.info(f"구조화된 텍스트 청킹 완료: {len(chunks)}개 청크")
            return chunks

        except Exception as e:
            logger.error(f"구조화된 텍스트 청킹 중 오류: {e}")
            return []

    def _format_markdown_row(self, row: List[str], headers: List[str]) -> str:
        """마크다운 행 포맷팅"""
        # 헤더 수에 맞춰 행 길이 조정
        formatted_row = list(row)
        while len(formatted_row) < len(headers):
            formatted_row.append("")

        # 특수 문자 이스케이프
        safe_cells = []
        for cell in formatted_row[: len(headers)]:
            if cell:
                safe_cell = str(cell).replace("|", "\\|").replace("\n", " ").strip()
                safe_cells.append(safe_cell)
            else:
                safe_cells.append("")

        return "| " + " | ".join(safe_cells) + " |"

    def _build_markdown_chunk(
        self, headers: List[str], rows: List[List[str]], sheet_name: str, chunk_num: int
    ) -> str:
        """마크다운 청크 생성 (헤더 보장)"""
        lines = []

        # 청크 제목
        if chunk_num > 1:
            lines.append(f"# {sheet_name} (Part {chunk_num})")
        else:
            lines.append(f"# {sheet_name}")
        lines.append("")

        # ⭐ 핵심: 테이블 헤더를 반드시 모든 청크에 포함
        header_line = "| " + " | ".join(headers) + " |"
        separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

        lines.append(header_line)
        lines.append(separator_line)

        # 데이터 행들 추가
        for row in rows:
            formatted_row = self._format_markdown_row(row, headers)
            lines.append(formatted_row)

        result = "\n".join(lines)
        return result

    def _build_structured_chunk(
        self, headers: List[str], rows: List[List[str]], sheet_name: str, chunk_num: int
    ) -> str:
        """구조화된 텍스트 청크 생성"""
        lines = []

        # 청크 제목
        if chunk_num > 1:
            lines.append(f"# {sheet_name} (Part {chunk_num})")
        else:
            lines.append(f"# {sheet_name}")
        lines.append("")
        lines.append(f"## 테이블 데이터 ({len(rows)}행)")
        lines.append("")

        # 각 행을 구조화된 형태로 변환
        for row_idx, row in enumerate(rows, 1):
            lines.append(f"### 항목 {row_idx}")

            for header, value in zip(headers, row):
                if value and str(value).strip():
                    clean_value = str(value).strip()
                    lines.append(f"- **{header}**: {clean_value}")

            lines.append("")  # 항목 간 구분

        return "\n".join(lines)

    def _build_structured_row_text(
        self, headers: List[str], row: List[str], row_num: int
    ) -> str:
        """단일 행의 구조화된 텍스트 생성"""
        lines = [f"### 항목 {row_num}"]

        for header, value in zip(headers, row):
            if value and str(value).strip():
                clean_value = str(value).strip()
                lines.append(f"- **{header}**: {clean_value}")

        lines.append("")
        return "\n".join(lines)

    def _create_empty_result(self, sheet_name: str) -> List[Dict]:
        """빈 결과 생성"""
        return [
            {
                "page_number": 1,
                "chunk_index": 0,
                "text": f"# {sheet_name}\n\n*(빈 시트)*",
                "row_count": 0,
                "type": "empty",
            }
        ]

    def _create_header_only_result(
        self, headers: List[str], sheet_name: str
    ) -> List[Dict]:
        """헤더만 있는 결과 생성"""
        content = f"# {sheet_name}\n\n**컬럼명**: " + ", ".join(headers)
        return [
            {
                "page_number": 1,
                "chunk_index": 0,
                "text": content,
                "row_count": 0,
                "type": "header_only",
            }
        ]

    def _create_error_result(self, sheet_name: str, error_msg: str) -> List[Dict]:
        """오류 결과 생성"""
        return [
            {
                "page_number": 1,
                "chunk_index": 0,
                "text": f"# {sheet_name}\n\n*(처리 오류: {error_msg})*",
                "row_count": 0,
                "type": "error",
            }
        ]
