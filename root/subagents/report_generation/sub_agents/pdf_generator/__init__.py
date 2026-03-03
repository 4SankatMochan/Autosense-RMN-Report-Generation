# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This project uses ReportLab (BSD License) for PDF generation.
# ReportLab: https://www.reportlab.com/
# ReportLab License: https://www.reportlab.com/software/opensource/
# Specifically uses: ReportLab PDF Toolkit (Open Source) and potentially json2pdf scaffolding.
from .pdf_generator import GCSJSONToPDF as JSONToPDF

__all__ = ["JSONToPDF"]
