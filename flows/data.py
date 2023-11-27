from collections import OrderedDict
from typing import OrderedDict
import pandas as pd
import os
import sys
import logging
from requests import HTTPError, ConnectionError
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
# from prefect import flow
from dotenv import load_dotenv

logging_level = logging.DEBUG
logging.basicConfig(stream=sys.stdout, level=logging_level)
logging.getLogger(__name__).addHandler(logging.StreamHandler(stream=sys.stdout))
load_dotenv(override=True)

DEBUG = int(os.getenv("DEBUG_APP2", 0))


class DataHandler:
    def __init__(self, entsoe_api_key):
        # see: https://github.com/EnergieID/entsoe-py#EntsoePandasClient
        self.e_client = EntsoePandasClient(entsoe_api_key)
        self.data = OrderedDict()
        self._init_data()

    def _init_data(self) -> None:
        self.data["df_generation"] = pd.DataFrame()
        self.data["df_generation_forecast"] = pd.Series()
        self.data["df_installed_capacity"] = pd.DataFrame()
        self.data["df_wind_and_solar_forecast"] = pd.DataFrame()
        self.df_current_generation = pd.Series()
        self.message = ""

    def get_new_data(self, country_code: str, forecast:bool=False) -> None:
        self._init_data()
        self.make_api_calls(country_code, forecast)
        self.clean_api_data()

    def read_instant_data(self, country_code: str) -> bool:
        try:
            for name, _ in self.data.items():
                self.data[name] = pd.read_pickle(f"./{name}_{country_code}.pkl")
        except Exception:
            return False
        return True

    # @cache_data
    def make_api_calls(self, country_code: str, forecast: bool =False) -> None:
        # just for development speed: read dataframes from disk
        if DEBUG and not forecast and self.read_instant_data(country_code):
            return
        # else:
        #     send_a_message_with_prefect(
        #         "info from prefect: app performs entsoe api call"
        #     )
        now = pd.Timestamp.today(tz="Europe/Brussels")
        start_t = now - pd.Timedelta(hours=24)
        if forecast:
            # start_t = now
            end_t = now + pd.Timedelta(hours=24)
        else:
            # start_t = now - pd.Timedelta(hours=24)
            end_t = now
        try:
            queries = [
                self.e_client.query_generation,
                self.e_client.query_generation_forecast,
                self.e_client.query_installed_generation_capacity,
                self.e_client.query_wind_and_solar_forecast,
            ]

            for df_name, query in zip(self.data.keys(), queries):
                #if forecast and not any(key in query.__name__ for key in ("forecast", "capacity")):
                #    continue
                self.data[df_name] = query(
                    country_code,
                    start=start_t
                    if "installed" not in query.__name__
                    else pd.Timestamp(
                        year=start_t.year, month=1, day=1, tz="Europe/Brussels"
                    ),
                    end=end_t
                    if "forecast" not in query.__name__
                    else end_t + pd.Timedelta(hours=12),
                )
            if DEBUG:
                for name, df in self.data.items():
                    df.to_pickle(f"./{name}_{country_code}.pkl")

        except NoMatchingDataError as e:
            self.message = f"""
                Error: Sorry, no data available for country: {country_code} 
                @ entsoe-API.
                {e}
            """
        except (HTTPError, ConnectionError) as e:
            self.message = f"""
                Error: Something went wrong with the http connection {e}
            """
        for key in self.data:
            logging.info(f"{key=}")
            logging.info(self.data[key].head())

    def clean_api_data(self) -> None:
        if "error" in self.message.lower():
            return
        # clean self.df_generation (fillna(0) already done in Entsoe Client)
        # take multiindex column names out
        try:
            df_cleaned_aggregation = self.data["df_generation"].swaplevel(axis=1)[
                "Actual Aggregated"
            ]  # df[:, 'Actual Aggregated']
            df_cleaned_consumption = self.data["df_generation"].swaplevel(axis=1)[
                "Actual Consumption"
            ]  # df[:, 'Actual Aggregated']
            common_columns = df_cleaned_aggregation.columns.intersection(
                df_cleaned_consumption.columns
            )
            df_cleaned_consumption.rename(
                columns={name: name + " (Consumption)" for name in common_columns},
                inplace=True,
            )
            # iloc[-4] because last ones are sometimes incomplete
            self.df_current_generation = df_cleaned_aggregation.iloc[-4]
            self.data["df_generation"] = pd.concat(
                [df_cleaned_aggregation, df_cleaned_consumption * (-1)]
            ).dropna(axis=1, how="all")
            del df_cleaned_aggregation
            del df_cleaned_consumption
        except TypeError:
            # some countries don't have multiindex column names
            if not self.data["df_generation"].empty:
                self.df_current_generation = self.data["df_generation"].iloc[-4]
            else:
                self.df_current_generation = pd.Series()
            
        try:
            # clean self.df_generation_forecast
            self.data["df_generation_forecast"].rename(
                "1 Day Ahead Forecast Total", inplace=True
            )
            
            forecast_begin = ( self.data["df_generation"].index[-1] 
                if not self.data["df_generation"].empty
                else pd.Timestamp.today(tz="Europe/Brussels") 
            )
                
            self.data["df_generation_forecast"] = self.data["df_generation_forecast"].loc[
                self.data["df_generation_forecast"].index
                > forecast_begin
            ]
            
            self.data["df_wind_and_solar_forecast"] = self.data[
                "df_wind_and_solar_forecast"
            ].loc[
                self.data["df_wind_and_solar_forecast"].index
                > forecast_begin
            ]
           
            
        except IndexError as e:
            logging.warning("IndexError occured, is dataframe empty?")

    def calculate_chart1_data(self) -> pd.DataFrame:
        if any(
            [
                self.data["df_generation"].empty,
                self.data["df_generation_forecast"].empty,
                self.data["df_wind_and_solar_forecast"].empty,
            ]
        ):
            return pd.DataFrame()

        # total forecast w/o wind an solar
        df_forecast_other = pd.DataFrame(
            self.data["df_generation_forecast"].to_frame()["1 Day Ahead Forecast Total"]
            - self.data["df_wind_and_solar_forecast"].sum(axis=1)
        )
        df_forecast_other.columns = ["Other"]
        df_forecast_other.dropna(inplace=True)

        df_forecast = pd.concat(
            [df_forecast_other, self.data["df_wind_and_solar_forecast"]],
            axis=1,
            join="inner",
        )
        chart_data = pd.concat([self.data["df_generation"], df_forecast])
        chart_data.rename_axis("Date", inplace=True)
        return chart_data

    def calculate_chart2_data(self) -> pd.DataFrame:
        if any(
            [
                self.data["df_installed_capacity"].empty,
                self.df_current_generation.empty,
            ]
        ):
            return pd.DataFrame()

        self.data["df_installed_capacity"].rename_axis(
            "Fuel", axis="columns", inplace=True
        )
        chart_data = pd.concat(
            [self.data["df_installed_capacity"].T, self.df_current_generation.T], axis=1,join="outer"
        ).fillna(0)
        chart_data.columns = ["capacity", "generated"]
        return chart_data


# @flow
# def send_a_message_with_prefect(text: str) -> None:
#     # just as first test:
#     print(text)
from prefect import task

@task
def extract_forecast_data_task(country_code: str, entsoe_api_key) -> OrderedDict[str,pd.DataFrame]:
    data_handler = DataHandler(entsoe_api_key)
    data_handler.get_new_data(country_code, forecast=True)
    data_handler.data["chart1_data"] = data_handler.calculate_chart1_data()
    data_handler.data["chart2_data"] = data_handler.calculate_chart2_data()
    return data_handler.data


if __name__ == "__main__":
    FORECAST = False

    data_handler = DataHandler(os.getenv("ENTSOE_API_KEY", ""))
    if FORECAST:
        data_handler.get_new_data("DE", forecast=True)
    else:
        data_handler.get_new_data("DE")


    print(data_handler.data["df_generation"].head())
    print(data_handler.data["df_generation_forecast"].head())
    print(data_handler.data["df_installed_capacity"])
    print(data_handler.data["df_wind_and_solar_forecast"].head())
    print(data_handler.df_current_generation)
    print(data_handler.calculate_chart1_data().head())
    print(data_handler.calculate_chart2_data())

    # import requests
    # from entsoe import EntsoeRawClient
    # request parameters:
    # params = {
    #     'securityToken': os.getenv("ENTSOE_API_KEY", ""),
    #     'periodStart': '202311120000' ,
    #     'periodEnd': '202311130000',
    #     'documentType': 'A68', # 'A75': 'Actual generation per type',
    #     'processType': 'A33',
    #     'in_Domain':'10Y1001A1001A82H' # default is Germany: '10Y1001A1001A83F'
    # }
    # url = 'https://web-api.tp.entsoe.eu/api'

    # response = requests.get(url=url, params=params)
    # print(response.text)
