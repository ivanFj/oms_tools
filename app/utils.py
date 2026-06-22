import asyncio
import datetime as dt
from oms_api import oms_api as oms
from oms_api import CountingMethods, Department, ItnTimeoutError, LoginFailedToAuthorize
import matplotlib.pyplot as plt
from aiohttp import ClientResponseError
import logger
import re

user: oms | None = None

async def create_user(cred: dict | None = None):
    global user
    try:
        user = await oms.authorize_access(cred)
    except LoginFailedToAuthorize as err:
        logger.critical(str(err))
        raise err
    except ValueError as err:
        logger.critical(str(err))
        raise err
    except TimeoutError as err:
        logger.critical(str(err))
        raise err

async def close_session():
    if user:
        await user.close_session() # type: ignore

async def group_jobs(data):
    job_groups = []
    current_group = []

    for i in range(len(data) + 1):
        if i != len(data):
            if data[i].upper().startswith("PHLABELS") and len(current_group) != 0:
                job_groups.append(current_group)
                current_group = []
                current_group.append(data[i])
            else:
                current_group.append(data[i])
        else:
            job_groups.append(current_group)

    return job_groups


async def print_qr_job(data):
    if not user: # type: ignore
        await create_user()
    
    tasks = []
    job_groups = await group_jobs(data)

    for job in job_groups:
        tasks += [user.print_qr_label(job[0], print_value) for print_value in job[1:]] # type: ignore

    for print_job in asyncio.as_completed(tasks):
        try:
            await print_job
        except ClientResponseError as err:
            logger.error("There was an issues with the request. The QR label failed to print.")
        except:
            logger.critical("Failed to print")
            raise

async def print_text_job(data):
    if not user: # type: ignore
        await create_user()
    
    tasks = []
    job_groups = await group_jobs(data)

    for job in job_groups:
        tasks += [user.print_text_label(job[0], print_value) for print_value in job[1:]] # type: ignore

    for print_job in asyncio.as_completed(tasks):
        try:
            await print_job
        except ClientResponseError as err:
            logger.error("There was an issues with the request. The text label failed to print.")
        except:
            logger.critical("Failed to print.")
            raise

async def print_itn_job(data):
    if not user: # type: ignore
        await create_user()
    
    tasks = []
    job_groups = await group_jobs(data)

    for job in job_groups:
        tasks += [user.print_rec_itn(job[0], print_value) for print_value in job[1:]] # type: ignore

    for print_job in asyncio.as_completed(tasks):
        try:
            await print_job
        except ClientResponseError as err:
            if not re.match("^[A-Z]{2}[0-9]{8}$", err.message):
                message = f"{err.message} is not an ITN with a valid format."
            else:
                #message = f"There was an issues with the request. The ITN {err.message} failed to print."
                message = f"ITN {err.message} does not exist in the system."
            logger.error(message)
            if len(tasks) == 1:
                raise Exception(message)
        except ItnTimeoutError as err:
            message = f"The request timed out. ITN, {err.itn}, failed to print."
            logger.error(message)
            if err.printer:
                await asyncio.sleep(3)
                await user.print_rec_itn(err.printer, err.itn) # type: ignore
            if len(tasks) == 1:
                raise Exception(message)
        except:
            message = "There was an unexpected error. Failed to print."
            logger.critical(message)
            if len(tasks) == 1:
                raise Exception(message)

async def get_production(functions: list[CountingMethods], department: str, start: dt.datetime, end: dt.datetime):
    if not user: # type: ignore
        await create_user()

    start = oms.convert_to_utciso(start)
    end = oms.convert_to_utciso(end)
    dept = Department[department.upper()]
    results = {}

    for func in functions:
        try:
            raw_data = await user.fetch_daily_production(func, start, end, dept) # type: ignore
            for event in raw_data['data']['taskCountByEventlogs']: # type: ignore
                name = event["User"].lower()
                if name not in results.keys():
                    results[name] = {}
                if func is CountingMethods.BY_ITNS:
                    results[name]["itns"] = int(event["total"])
                elif func is CountingMethods.BY_POS:
                    results[name]["pos"] = int(event["total"])
        except ClientResponseError as err:
            message = f"Failed to get data on {dept.name} - {func.value}"
            logger.error(message)
            raise Exception(message)
        except:
            message = "There was an error with fetching production data."
            logger.critical(message)
            raise Exception(message)
        
    production_df = [["Associate", "ITNs", "POs"]]
    for k, v in results.items():
        production_df.append([k, v.get("itns", 0), v.get("pos", 0)])

    table_colors = []
    for i in range(len(production_df)):
        if i % 2 == 0:
            table_colors.append(["#90B0EE" for j in range(len(production_df[i]))])
        else:
            table_colors.append(["white" for j in range(len(production_df[i]))])

    table = plt.table(production_df, table_colors, cellLoc = "center", loc = "center")
    plt.gcf().set_size_inches((6, 5))
    plt.gcf().tight_layout()
    plt.axis("off")
    plt.show()
    
async def get_itn_info(itns):
    if not user: # type: ignore
        await create_user()

    leftover_itns = []
    retrived_itns = []
    tasks = [user.fetch_itn_info(itn) for itn in itns] # type: ignore
    for fetch_job in asyncio.as_completed(tasks):
        try:
            result = await fetch_job
            retrived_itns.append(result)
        except ClientResponseError as err:
            retrived_itns.append(err)
        except ItnTimeoutError as e:
            leftover_itns.append(e.itn)
        except:
            logger.critical("Failed to get ITN information.")
            raise Exception("Failed to get ITN information.")
    return retrived_itns, leftover_itns