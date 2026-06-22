import aiohttp
import asyncio
import playwright.async_api as paa
from playwright.async_api import async_playwright
import playwright.async_api as playwright_api
from datetime import timedelta
from enum import Enum

CREDENTIALS = {"username" : "XXXX", "password" : "XXXX"}

class ItnTimeoutError(asyncio.TimeoutError):
    def __init__(self, itn, printer = None):
        self.itn = itn
        self.printer = printer
        super().__init__()

class LoginFailedToAuthorize(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class EventID(Enum):
    QC_DONE = 202
    PICKING_DONE = 309
    LINE_PICKED = 810
    AUTOSTORE = 3025
    SKIPPED_ITNS = 3027
    LOC_SCANNED = 3030
    GENERATE_ITN = 1130
    UPDATE_INVENTORY = 1140

class CountingMethods(Enum):
    BY_ITNS = "InventoryTrackingNumber"
    BY_POS = "PurchaseOrderNumber"

class Department(Enum):
    RECEIVING = 1140

class Printer(dict):
    def __init__(self, printer_info:dict):
        self["dpi"] = str(printer_info["data"]["findPrinters"][0]["DPI"])
        orientation = printer_info["data"]["findPrinters"][0]["Orientation"]
        self["orientation"] = "LANDSCAPE" if orientation == "L" else "PORTRAIT"
        self["printer"] = printer_info["data"]["findPrinters"][0]["Name"]

class oms_api:
    _login_url = ""
    _auth_url = ""
    _oms_url = ""
    _auth_header = {"Authorization" : "", "Content-Type": "application/json"}
    _cred = CREDENTIALS
    _session: aiohttp.ClientSession | None = None
    _other_session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession | None:
        return self._session
    
    @session.setter
    def session(self, http_session):
        self._session = http_session

    def __init__(self, login = None) -> None:
        if login:
            self._cred = login

    @classmethod
    async def authorize_access(cls, login: dict | None = None):
        if login:
            if not login["username"] or not login["password"]:
                raise ValueError("Missing username and/or password")
            else:
                self = cls(login)
        else:
            self = cls()

        async with async_playwright() as p:

            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            await page.goto(self._login_url)
            username = page.locator("input[name='username']")
            password = page.locator("input[name='password']")
            await username.fill(self._cred["username"])
            await password.fill(self._cred["password"])

            try:
                async with page.expect_response(self._auth_url, timeout = 20000) as response_info:
                    await page.locator("button[type='submit']").click()
            except playwright_api.TimeoutError:
                raise TimeoutError("Login attempt timed out.")
                
            response = await response_info.value
            if response.ok:
                validation_response = await response.json()
                id_token = validation_response['idToken']
                self._auth_header["Authorization"] = "Bearer " + id_token
                self.session = aiohttp.ClientSession(headers = self._auth_header)
                return self
            
            else:
                raise LoginFailedToAuthorize("Authorization failed. Please check the username and/or password")

    async def close_session(self):
        if self.session:
            await self.session.close()
        if self._other_session:
            await self._other_session.close()
        return None

    @staticmethod
    def convert_to_utciso(time):
        temp = time + timedelta(hours = 7)
        converted_time = temp.isoformat()
        return converted_time.split(".")[0] + ".000Z"
    
    async def get_printer_info(self, name):
        if self.session:
            request_body = {"operationName" : "fetchPrinterByName", "variables" : {"name": name}, "query" : "query fetchPrinterByName($name: String!) {\n  findPrinters(Printer: {Name: $name}) {\n    Name\n    Orientation\n    DPI\n    StationName\n    __typename\n  }\n}"}
            async with self.session.post(self._oms_url, json = request_body) as response:
                try:
                    response.raise_for_status()
                except aiohttp.ClientResponseError as err:
                    raise aiohttp.ClientResponseError(err.request_info, err.history, message = f"Printer {name} was not found.")
                
                response_body = await response.json()
                try:
                    response_body["data"]["findPrinters"][0]
                except IndexError as err:
                    raise aiohttp.ClientResponseError(response.request_info, response.history, message = f"Printer {name} not found.")

                return response_body

    async def fetch_daily_production(self, dc_function: CountingMethods, start_time: str, end_time: str, event_id: Department):
        result = None

        if self.session:
            request_body = {"operationName": "table_taskCountByEventlogs", "variables": {"countBy": dc_function.value, "eventTypeIds": [event_id.value], "daterange": {"from": start_time, "to": end_time}}, "query": "query table_taskCountByEventlogs($daterange: DateRange!, $eventTypeIds: [Int]!, $countBy: String!) {\n  taskCountByEventlogs(\n    daterange: $daterange\n    eventTypeIds: $eventTypeIds\n    countBy: $countBy\n  ) {\n    User\n    total\n    taskCounter\n    __typename\n  }\n}"}
            async with self.session.post(url = self._oms_url, json = request_body) as response:

                try:
                    response.raise_for_status()
                except aiohttp.ClientResponseError as err:
                    raise aiohttp.ClientResponseError(err.request_info, err.history, message = await response.text())        
                result = await response.json()

            return result

    async def fetch_itn_info(self, itn: str):
        if self.session:
            request_body = {"operationName" : "BarcodeSearch_ItnInfo", "variables" : {"DistributionCenter" : "PH", "InventoryTrackingNumber" : itn}, "query" : "query BarcodeSearch_ItnInfo($DistributionCenter: String!, $InventoryTrackingNumber: String!) {\n  inventory(\n    DistributionCenter: $DistributionCenter\n    InventoryTrackingNumber: $InventoryTrackingNumber\n  ) {\n    DistributionCenter\n    InventoryTrackingNumber\n    QuantityOnHand\n    DateCode\n    ParentITN\n    ROHS\n    OriginalQuantity\n    BinLocation\n    NotFound\n    Country {\n      CountryCode\n      CountryName\n      ISO2\n      ISO3\n      __typename\n    }\n    Container {\n      Barcode\n      Zone\n      Warehouse\n      Row\n      Aisle\n      Section\n      Shelf\n      ShelfDetail\n      ContainerType {\n        Name\n        IsMobile\n        __typename\n      }\n      USERINFOs {\n        Name\n        __typename\n      }\n      __typename\n    }\n    Product {\n      PartNumber\n      ProductTier\n      Velocity\n      ProductCode {\n        ProductCodeNumber\n        __typename\n      }\n      PURCHASEORDERLs {\n        PurchaseOrderH {\n          PurchaseOrderNumber\n          __typename\n        }\n        __typename\n      }\n      RECEIPTLs {\n        LineNumber\n        ExpectedQuantity\n        ReceiptH {\n          ExpectedArrivalDate\n          ReceiptNumber\n          Vendor {\n            VendorName\n            VendorNumber\n            __typename\n          }\n          __typename\n        }\n        RECEIPTLDs {\n          ExpectedQuantity\n          ReceiptStatus {\n            Name\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    ORDERLINEDETAILs {\n      Quantity\n      BinLocation\n      WMSPriority\n      Status {\n        Name\n        __typename\n      }\n      OrderLine {\n        OrderLineNumber\n        Quantity\n        __typename\n      }\n      OrderHeader {\n        OrderNumber\n        NOSINumber\n        OrderType\n        isSelected\n        ShipmentMethod {\n          ShippingMethod\n          PriorityPinkPaper\n          __typename\n        }\n        Customer {\n          CustomerNumber\n          CustomerTier\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}"}
            try:
                async with self.session.post(self._oms_url, json = request_body) as response:
                    try:
                        response.raise_for_status()
                    except aiohttp.ClientResponseError as err:
                        raise aiohttp.ClientResponseError(err.request_info, err.history, message = itn)
                    
                    response_body = await response.json()
                    try:
                        response_body["data"]["inventory"]["InventoryTrackingNumber"]
                    except (KeyError, TypeError) as err:
                        raise aiohttp.ClientResponseError(response.request_info, response.history, message = f"{itn} does not exist")

                    response_body["data"]["inventory"]["itn"] = itn
                    return response_body
            except asyncio.TimeoutError as err:
                raise ItnTimeoutError(itn)
        
    async def fetch_event_logs(self, start_time: str, end_time: str, *dc_function: EventID, user: str = "", skip = 0, take = 500):
        if self.session:
            headers = {"Content-Type" : "application/json"}
            request_variables = {"eventLogInput": {"eventTypeIds": [], "createdAt": {"from": start_time, "to": end_time}}, "pagination": {"skip": skip, "take": take}}

            if not self._other_session: 
                self._other_session = aiohttp.ClientSession(headers = self._auth_header | headers)

            if not user and not dc_function:
                raise ValueError("Username and/or the type of DC activity must be provided.")
            
            if user:
                request_variables["eventLogInput"]["userName"] = user

            if dc_function:
                for name in dc_function:
                    request_variables["eventLogInput"]["eventTypeIds"].append(name.value)

            request_body = {"operationName": "EventLogs", "variables": request_variables, "query": "query EventLogs($eventLogInput: SearchEventLogInput, $pagination: Pagination) {\n  EventLogs(EventLogInput: $eventLogInput, Pagination: $pagination) {\n    _id\n    eventTypeId\n    userName\n    log\n    createdAt\n    __typename\n  }\n}"}
            async with self._other_session.post(url = self._oms_url, json = request_body) as response:
                try:
                    response.raise_for_status()
                except aiohttp.ClientResponseError as err:
                    raise err
                
                return await response.json()
    
    async def print_rec_itn(self, printer:str, itn_number: str):
        if self.session:
            try:
                itn_number = itn_number.strip().upper()
                itn_info = await self.fetch_itn_info(itn_number)
                part_number:str = itn_info["data"]["inventory"]["Product"]["PartNumber"] # type: ignore
                prc:str = itn_info["data"]["inventory"]["Product"]["ProductCode"]["ProductCodeNumber"] # type: ignore
                printer_info = Printer(await self.get_printer_info(printer.upper())) # type: ignore

                request_variables = {"DPI": printer_info["dpi"], "ITN": itn_number, "ORIENTATION": printer_info["orientation"], "PARTNUMBER": part_number.strip().upper(), "PRINTER": printer_info["printer"].upper(), "PRODUCTCODE": prc.strip().upper()}
                request_body = {"operationName": "printing_receivingITNLabel", "variables": request_variables, "query": "query printing_receivingITNLabel($PRINTER: String!, $ITN: String!, $PRODUCTCODE: String!, $PARTNUMBER: String!, $DPI: String!, $ORIENTATION: String!) {\n  printReceivingITNLabel(\n    PRINTER: $PRINTER\n    ITN: $ITN\n    DPI: $DPI\n    PRODUCTCODE: $PRODUCTCODE\n    PARTNUMBER: $PARTNUMBER\n    ORIENTATION: $ORIENTATION\n  )\n}"}
                async with self.session.post(self._oms_url, json = request_body) as response:
                    response.raise_for_status()
            except aiohttp.ClientResponseError as err:
                raise aiohttp.ClientResponseError(err.request_info, err.history, message = itn_number)
            except ItnTimeoutError as err:
                raise ItnTimeoutError(itn_number, printer)
        
            return None
    
    async def print_qr_label(self, printer: str, text: str):
        if self.session:
            printer_info = Printer(await self.get_printer_info(printer.upper())) # type: ignore
            request_variables = {"DPI": printer_info["dpi"], "ORIENTATION": printer_info["orientation"], "PRINTER": printer_info["printer"].upper(), "TEXT": text}
            request_body = {"operationName": "printing_QRCodeLabel", "variables": request_variables, "query": "query printing_QRCodeLabel($PRINTER: String!, $DPI: String!, $ORIENTATION: String!, $TEXT: String!) {\nprintQRCodeLabel(\nPRINTER: $PRINTER\n DPI: $DPI\n ORIENTATION: $ORIENTATION\n TEXT: $TEXT\n)\n}"}
            async with self.session.post(self._oms_url, json = request_body) as response:

                try:
                    response.raise_for_status()
                except aiohttp.ClientResponseError as err:
                    raise err
                except aiohttp.ClientConnectionError as err:
                    raise err
        
                return await response.json()
    
    async def print_text_label(self, printer: str, text: str):
        if self.session:
            printer_info = Printer(await self.get_printer_info(printer.upper())) # type: ignore
            text = " ".join(text.split())
            print(text)
            lines = []
            last_i = 0
            max_char_length = 23
            current_i = max_char_length
            if len(text) > max_char_length:
                while current_i < len(text):
                    if text[current_i] == " ":
                        lines.append(text[last_i:current_i])
                        last_i = current_i + 1
                    else:
                        tempi = text[last_i:current_i].rfind(" ") + last_i
                        tempi = text[last_i:].find(" ") + last_i if tempi == -1 else tempi
                        tempi = len(text) if tempi == -1 else tempi
                        lines.append(text[last_i:tempi])
                        last_i = tempi + 1
                    current_i = last_i + max_char_length
                    if current_i > len(text):
                        lines.append(text[last_i:])
            else:
                lines.append(text)

            def _format_variables(line1 = "", line2 = "", line3 = "", line4 = ""):
                return {"LINE1": line1, "LINE2": line2, "LINE3": line3, "LINE4": line4}

            request_variables = {"DPI": printer_info["dpi"], "ORIENTATION": printer_info["orientation"], "PRINTER": printer_info["printer"].upper()} | _format_variables(*lines)
            request_body = {"operationName": "printing_textLabel", "variables": request_variables, "query": "query printing_textLabel($PRINTER: String!, $DPI: String!, $ORIENTATION: String!, $LINE1: String!, $LINE2: String!, $LINE3: String!, $LINE4: String!) {\nprintTextLabel(\nPRINTER: $PRINTER\n DPI: $DPI\n ORIENTATION: $ORIENTATION\n LINE1: $LINE1\n LINE2: $LINE2\n LINE3: $LINE3\n LINE4: $LINE4\n)\n}"}
            async with self.session.post(self._oms_url, json = request_body) as response:

                try:
                    response.raise_for_status()
                except aiohttp.ClientResponseError as err:
                    raise err
        
                return await response.json()
            
    
