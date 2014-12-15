Tryton SQS Async Execution
==========================

This module helps you use Amazon SQS and workers to asynchronously
execute long running and blocking tasks.

Quickstart
----------

::

    from trytond.modules.async_sqs import async_task

    class MyBigReport(Report):
        __name__ = 'report.bigreport'

        @async_task()
        def expensive_method(self, arg1, arg2):
            """
            An expensive method which determines your future
            """
            # do something hard and figure it out
            return your_future
        

Now that the method `expensive_method` is decorated with async, your old
code will continue to work as expected::

    # Slow, synchronous execution in same computer
    Pool().get('report.bigreport').expensive_method(1, 2)

To execute the same report asynchronously, on a worker::

    Pool().get('report.bigreport').expensive_method(1, 2, _defer_=True)

How about Results
-----------------

For best results, asynchronous architecures should not wait for results
where not required. However, that may not work in all situations. 

So results are sent back after creating a new queue with a name generated
from a uuid which both the client and the worker have pre-agreed.


Step 1 is to explicitly decorate the task as one that needs the result.

::

        @async_task(ignore_result=False)
        def expensive_method(self, arg1, arg2):
            """
            An expensive method which determines your future
            """
            # do something hard and figure it out
            return your_future

To wait until the result is computed and returned::

    result = sync_results.wait()

To wait just 10 seconds and forget if not received::

    result = sync_results.wait(10)

The result can be received only once.

Why do I need this ?
--------------------

For Tryton
``````````

Depending on the nature of your usage, there could be operations like
reports which take a long time to complete. These may even hog CPU and
memory affecting others using Tryton on the same server (VM). Using a
message queue and running workers, these tasks can be offloaded to a
cluster of workers to remotely execute.

For Nereid
``````````

Even small tasks like sending emails could affect the scalability and
experience of users on your web portal. You coudl use this module to
offload blocking tasks to workers and asynchronously respond to requests.

A big fat warning
-----------------

Thinking and executing asynchronously on Tryton (or any framework in
general) requires a good understanding of the framework, the way
transactions are handled and the request-response cycle. If you do not,
you should probably dig into the framework internals before using async in
your projects.

Installation
------------

::

    pip install openlabs_trytond_async_sqs

Configuration
-------------

All of the configuration for SQS is done from the `trytond.conf` file of
your project.

=================== ========================================================
Config option       Description
=================== ========================================================
sqs_region          (Optional) defaults to boto default
sqs_access_key      (Required) specify in config or env (see below)
sqs_secret_key      (Required) specify in config or env (see below)
sqs_queue           (Optional) Name of the queue 
                    (Default: `trytond-async`)
sqs_queue_owner     (Optional)
sqs_queue_prefix    A prefix to use when creating queues (if its a
                    multi-tenant setup.) 
=================== ========================================================


Configuring Boto
`````````````````

It is certainly a better option not to have you access_key and secret in
the tryton configuration file. To configure boto using environment
variables or a config file in your home directory read the documentation
of boto.

Read more: http://boto.readthedocs.org/en/latest/boto_config_tut.html


Known Issues
````````````

The python `@classmethod` assumes in the implementation of its `__get__()` method
that the wrapped function is a normal function and breaks the descriptor protocol.

To get around this, you should place the `async_task` decorator outside of the
`@classmethod` decorator and never inside.

Example::

    class MyBigReport(Report):
        __name__ = 'report.bigreport'

        @async_task()
        @classmethod
        def expensive_method(cls, arg1, arg2):
            """
            An expensive method which determines your future
            """
            # do something hard and figure it out
            return your_future

Read more: `http://wrapt.readthedocs.org/en/latest/issues.html#classmethod-get`_

TODO
````

One of the ugly (ahem!) aspects of the API currently is the need to pass
the keyword argument `_defer_` to pass the task. A better syntax would be
like the celery api 
`Pool().get('report.bigreport').expensive_method.defer(1, 2)`. If you have
any ideas on how this could be done, pull requests are welcome.