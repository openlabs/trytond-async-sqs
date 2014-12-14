# -*- coding: UTF-8 -*-
"""
    trytond_async_sqs.worker

    Worker helper classes to implement workers

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) LTD
    :license: 3-clause BSD License, see COPYRIGHT for more details
"""
import logging

from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction

logger = logging.getLogger('AsyncSQS')


class Listener(object):
    """
    Listen to the task queue for a given daatabase
    """
    def __init__(self, database_name, prefetch_messages=1):
        Database = backend.get('Database')
        self.database_name = database_name
        self.database = Database(database_name).connect()
        self.pool = Pool(database_name)
        if 'model' not in self.pool._pool:
            logger.info('Initializing pool')
            self.pool.init()

        self.prefetch_messages = prefetch_messages

    def listen(self):
        """
        Listen to the queue where tasks would be queued
        """
        Async = self.pool.get('async.async')

        with Transaction().start(self.database_name, 0, readonly=True):
            queue = Async.get_queue()

        while True:
            logger.info('Liseting to queue for new messages.')
            messages = queue.get_messages(
                self.prefetch_messages,
                wait_time_seconds=20
            )
            logger.info('Received %d messages.' % len(messages))
            for message in messages:
                self.execute_message(message)
                queue.delete_message(message)

    def execute_message(self, message):
        """
        Execute the task by calling the async model
        """
        Async = self.pool.get('async.async')

        with Transaction().start(self.database_name, 0, readonly=True):
            # Serializing the payload on a readonly transaction
            # without any context to get the user, database and context
            # on which the transaction should really be executed.
            payload = Async.deserialize_message(message.get_body())
            assert payload['database_name'] == self.database_name

        with Transaction().start(
                self.database_name,
                payload['user'],
                context=payload['context']) as transaction:
            # Deserialize the message again because active records live
            # within the same transaction.
            payload = Async.deserialize_message(message.get_body())
            try:
                logger.debug("Message body: %s" % payload)
                result = Async.execute_task(payload)
            except Exception, exc:
                logger.error("Transaction Rollback due to failure")
                logger.error(exc)
                transaction.cursor.rollback()
            else:
                logger.debug("Task Succesful")
                logger.debug(result)
                transaction.cursor.commit()
                return result


if __name__ == '__main__':
    from trytond.config import CONFIG
    import argparse
    parser = argparse.ArgumentParser(
        description='Simple Worker for Trytond Async SQS'
    )
    parser.add_argument('database', help="Name of the database")
    parser.add_argument(
        '--config', dest='config',
        help="Path to tryton config"
    )
    args = parser.parse_args()

    if args.config:
        CONFIG.update_etc(args.config)

    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    logger.debug('Hello')

    listener = Listener(args.database)
    listener.listen()
