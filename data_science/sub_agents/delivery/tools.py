# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Delivery tool to send structured response to client/UI.
"""

import json

def send_response_to_ui(response: dict) -> dict:
    """
    Simulates sending structured insight to a client or dashboard.

    Args:
        response: Final structured narrative as dict.

    Returns:
        The response (for confirmation or logging).
    """
    print("\n🚀 Sending Structured Response to UI:")
    print(json.dumps(response, indent=2))
    return response
