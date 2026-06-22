from oms_api import oms_api as oms
from oms_api import Printer
import asyncio
import argparse
from aiohttp.client_exceptions import ClientResponseError
import traceback

class oms_print:
    user:oms

    def __init__(self):
        pass

    @classmethod
    async def main_runner(cls, method, data, printer_num = None):
        self = cls()
        self.user = await oms.authorize_access()

        if not printer_num:
            tasks = []
            for print_data in data:
                tasks.append(method(print_data[0], print_data[1:]))
            
            for print_job in asyncio.as_completed(tasks):
                try:
                    await print_job
                except ClientResponseError as err:
                    print(err.message)
                    traceback.print_exc()
        else:
            if len(data) == 1:
                await method(self, printer_num, data)
            else:
                tasks = []
                for print_data in data:
                    tasks.append(method(self, printer_num, print_data))
                
                for print_job in asyncio.as_completed(tasks):
                    try:
                        await print_job
                    except ClientResponseError as err:
                        print(err.message)
                        traceback.print_exc()

        await self.user.close_session()

    async def text_label(self, printer, data):
        await self.user.print_text_label(printer, *data)

    async def qr_label(self, printer, data):
        await self.user.print_qr_label(printer, " ".join(data))

    async def itn_label(self, printer, data):
        tasks = [self.user.print_rec_itn(printer, itn.upper()) for itn in data]
        for t in asyncio.as_completed(tasks):
            try:
                await t
            except ClientResponseError as err:
                print(err.message)
                traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Script to print QR or text labels or ITNS.")
    parser.add_argument("-m", "--multiple", action = "store_true", help = "If printing to multiple printers or multiple lables, this flag groups data into (printer, label1, label2,...etc).")
    exclusive_group = parser.add_mutually_exclusive_group(required = True)
    exclusive_group.add_argument("-t", "--text", action = "store_true", help = "Print a text label.")
    exclusive_group.add_argument("-q", "--qr", action = "store_true", help = "Print a qr code label with text.")
    exclusive_group.add_argument("-i", "--itn", action = "store_true", help = "Print an ITN label.")
    parser.add_argument("printer_num", help = "The number of the printer to print to.")
    parser.add_argument("data", nargs = "+", help = "The data needed to print on the label (text or ITN)")
    args = parser.parse_args()

    method = None
    if args.text:
        method = oms_print.text_label
    elif args.qr:
        method = oms_print.qr_label
    elif args.itn:
        method = oms_print.itn_label

    if args.multiple:
        multiple_print = []
        raw_data = args.data
        current_group = [args.printer_num]
        for d in raw_data:
            try:
                int(d)
                multiple_print.append(current_group)
                current_group = []
            except ValueError:
                pass
            finally:
                current_group.append(d)
        multiple_print.append(current_group)
        if len(multiple_print) > 1:
            asyncio.run(oms_print.main_runner(method, multiple_print))
        else:
            asyncio.run(oms_print.main_runner(method, args.data, args.printer_num))
    else:
        asyncio.run(oms_print.main_runner(method, args.data, args.printer_num))