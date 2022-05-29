import configparser
from datetime import datetime
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col
from pyspark.sql.functions import year, month, dayofmonth, hour, weekofyear, date_format


config = configparser.ConfigParser()
config.read('dl.cfg')

os.environ['AWS_ACCESS_KEY_ID']=config.get('AWS','AWS_ACCESS_KEY_ID')
os.environ['AWS_SECRET_ACCESS_KEY']=config.get('AWS','AWS_SECRET_ACCESS_KEY')


def create_spark_session():
    """
        Description: The function creates a spark session.
    """
    spark = SparkSession \
        .builder \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:2.7.0") \
        .getOrCreate()
    return spark


def process_song_data(spark, input_data, output_data):
    """
        Description: The function extracts and transforms songs table and 
                     artists table from the song data in S3, and load the tables back
                     to S3.
        
        Parameters:
            spark       : Spark Session
            input_data  : the location of the input data
            output_data : the locaton where the results are stored
            
    """
    # get filepath to song data file
    song_data = input_data + 'song_data/*/*/*/*.json'
    
    # read song data file
    df = spark.read.json(song_data)
    
    # created song view to write SQL Queries
    df.createOrReplaceTempView("song_data_table")

    # extract columns to create songs table
    songs_table = spark.sql("""
                            SELECT song_id, 
                            title,
                            artist_id,
                            year,
                            duration
                            FROM song_data_table
                            WHERE song_id IS NOT NULL
                        """)
    
    # write songs table to parquet files partitioned by year and artist
    songs_table.write.mode('overwrite').partitionBy("year", "artist_id").parquet(output_data+'songs_table/')

    # extract columns to create artists table
    artists_table = spark.sql("""
                                SELECT DISTINCT artist_id, 
                                artist_name,
                                artist_location,
                                artist_latitude,
                                artist_longitude
                                FROM song_data_table
                                WHERE artist_id IS NOT NULL
                            """)
    
    
    # write artists table to parquet files
    artists_table.write.mode('overwrite').parquet(output_data+'artists_table/')


def process_log_data(spark, input_data, output_data):
    """
        Description: The function extracts and transforms users table, time table, 
                     songplays table from the log data in S3, and load the tables back
                     to S3.
        
        Parameters:
            spark       : Spark Session
            input_data  : the location of the input data
            output_data : the locaton where the results are stored
            
    """
    
    # get filepath to log data file
    log_path = input_data + 'log_data/*.json'

    # read log data file
    df = spark.read.json(log_path)
    
    # filter by actions for song plays
    df = df.filter(df.page == 'NextSong')
    
    # created log view to write SQL Queries
    df.createOrReplaceTempView("log_data_table")

    # extract columns for users table    
    users_table = spark.sql("""
                            SELECT DISTINCT userId as user_id, 
                            firstName as first_name,
                            lastName as last_name,
                            gender as gender,
                            level as level
                            FROM log_data_table
                            WHERE userId IS NOT NULL
                        """)
    
    # write users table to parquet files
    users_table.write.mode('overwrite').parquet(output_data+'users_table/')
    
    # extract columns to create time table
    time_table = spark.sql("""
                            SELECT 
                            temp.time as start_time,
                            hour(temp.time) as hour,
                            dayofmonth(temp.time) as day,
                            weekofyear(temp.time) as week,
                            month(temp.time) as month,
                            year(temp.time) as year,
                            dayofweek(temp.time) as weekday
                            FROM
                            (SELECT to_timestamp(log.ts/1000) as time
                            FROM log_data_table log
                            WHERE log.ts IS NOT NULL
                            ) temp
                        """)
    
    # write time table to parquet files partitioned by year and month
    time_table.write.mode('overwrite').partitionBy("year", "month").parquet(output_data+'time_table/')

    # read in song data to use for songplays table
    song_df = spark.read.parquet(output_data+'songs_table/')

    # extract columns from joined song and log datasets to create songplays table 
    songplays_table = spark.sql("""
                                SELECT monotonically_increasing_id() as songplay_id,
                                to_timestamp(logT.ts/1000) as start_time,
                                month(to_timestamp(log.ts/1000)) as month,
                                year(to_timestamp(log.ts/1000)) as year,
                                log.userId as user_id,
                                log.level as level,
                                song.song_id as song_id,
                                song.artist_id as artist_id,
                                log.sessionId as session_id,
                                log.location as location,
                                log.userAgent as user_agent
                                FROM log_data_table log
                                JOIN song_data_table song on log.artist = song.artist_name and log.song = song.title
                            """)

    # write songplays table to parquet files partitioned by year and month
    songplays_table.write.mode('overwrite').partitionBy("year", "month").parquet(output_data+'songplays_table/')


def main():
    spark = create_spark_session()
    
    input_data = "s3://udacity-dend/data/"
    output_data = "s3://udacity-dend/results/"
    
    process_song_data(spark, input_data, output_data)    
    process_log_data(spark, input_data, output_data)


if __name__ == "__main__":
    main()