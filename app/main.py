import ui_builder as ui
import qasync as qa
import asyncio
import logger
import qt_material as material


if __name__ == "__main__":
    logger.set_logger_config("oms.log")

    app = qa.QApplication([])
    material.apply_stylesheet(app, "dark_blue.xml")
    event_loop = qa.QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    app.setStyle("fusion")
    main_window = ui.MainWindow()
    main_window.build_app()
    main_window.show()
    

    with event_loop:
        event_loop.run_until_complete(app_close_event.wait())

