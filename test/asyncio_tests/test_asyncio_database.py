# Copyright 2014 MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test AsyncIOMotorDatabase."""

import unittest

import pymongo.database
from bson import CodecOptions
from bson.binary import JAVA_LEGACY
from pymongo import ReadPreference, WriteConcern
from pymongo.errors import CollectionInvalid, OperationFailure
from pymongo.read_preferences import Secondary

from motor.motor_asyncio import (AsyncIOMotorCollection, AsyncIOMotorDatabase)
from test import env
from test.asyncio_tests import (AsyncIOTestCase, asyncio_test)


class TestAsyncIODatabase(AsyncIOTestCase):
    @asyncio_test
    async def test_database(self):
        # Test that we can create a db directly, not just get on from
        # AsyncIOMotorClient.
        db = AsyncIOMotorDatabase(self.cx, 'motor_test')

        # Make sure we got the right DB and it can do an operation.
        self.assertEqual('motor_test', db.name)
        await db.test_collection.delete_many({})
        await db.test_collection.insert_one({'_id': 1})
        doc = await db.test_collection.find_one({'_id': 1})
        self.assertEqual(1, doc['_id'])

    @asyncio_test
    async def test_database_subclass(self):
        class MyDB(AsyncIOMotorDatabase):
            async def ping(self):
                return await self.command('ping')
        db = MyDB(self.cx, 'motor_test')
        res = await db.ping()
        self.assertTrue(res['ok'])

    def test_collection_named_delegate(self):
        db = self.db
        self.assertTrue(isinstance(db.delegate, pymongo.database.Database))
        self.assertTrue(isinstance(db['delegate'], AsyncIOMotorCollection))
        db.client.close()

    def test_call(self):
        # Prevents user error with nice message.
        try:
            self.cx.foo()
        except TypeError as e:
            self.assertTrue('no such method exists' in str(e))
        else:
            self.fail('Expected TypeError')

    @env.require_version_min(3, 6)
    @asyncio_test
    async def test_aggregate(self):
        pipeline = [{"$listLocalSessions": {}},
                    {"$limit": 1},
                    {"$addFields": {"dummy": "dummy field"}},
                    {"$project": {"_id": 0, "dummy": 1}}]
        expected = [{"dummy": "dummy field"}]

        cursor = self.cx.admin.aggregate(pipeline)
        docs = await cursor.to_list(10)
        self.assertEqual(expected, docs)

    @asyncio_test
    async def test_command(self):
        result = await self.cx.admin.command("buildinfo")
        # Make sure we got some sane result or other.
        self.assertEqual(1, result['ok'])

    @asyncio_test
    async def test_create_collection(self):
        # Test creating collection, return val is wrapped in
        # AsyncIOMotorCollection, creating it again raises CollectionInvalid.
        db = self.db
        await db.drop_collection('test_collection2')
        collection = await db.create_collection('test_collection2')
        self.assertTrue(isinstance(collection, AsyncIOMotorCollection))
        self.assertTrue(
            'test_collection2' in (await db.list_collection_names()))

        with self.assertRaises(CollectionInvalid):
            await db.create_collection('test_collection2')

    @asyncio_test
    async def test_drop_collection(self):
        # Make sure we can pass an AsyncIOMotorCollection instance to
        # drop_collection.
        db = self.db
        collection = db.test_drop_collection
        await collection.insert_one({})
        names = await db.list_collection_names()
        self.assertTrue('test_drop_collection' in names)
        await db.drop_collection(collection)
        names = await db.list_collection_names()
        self.assertFalse('test_drop_collection' in names)

    @asyncio_test
    async def test_validate_collection(self):
        db = self.db

        with self.assertRaises(TypeError):
            await db.validate_collection(5)
        with self.assertRaises(TypeError):
            await db.validate_collection(None)
        with self.assertRaises(OperationFailure):
            await db.validate_collection("test.doesnotexist")
        with self.assertRaises(OperationFailure):
            await db.validate_collection(db.test.doesnotexist)

        await db.test.insert_one({"dummy": "object"})
        self.assertTrue((await db.validate_collection("test")))
        self.assertTrue((await db.validate_collection(db.test)))

    def test_get_collection(self):
        codec_options = CodecOptions(
            tz_aware=True, uuid_representation=JAVA_LEGACY)
        write_concern = WriteConcern(w=2, j=True)
        coll = self.db.get_collection(
            'foo', codec_options, ReadPreference.SECONDARY, write_concern)

        self.assertTrue(isinstance(coll, AsyncIOMotorCollection))
        self.assertEqual('foo', coll.name)
        self.assertEqual(codec_options, coll.codec_options)
        self.assertEqual(ReadPreference.SECONDARY, coll.read_preference)
        self.assertEqual(write_concern, coll.write_concern)

        pref = Secondary([{"dc": "sf"}])
        coll = self.db.get_collection('foo', read_preference=pref)
        self.assertEqual(pref, coll.read_preference)
        self.assertEqual(self.db.codec_options, coll.codec_options)
        self.assertEqual(self.db.write_concern, coll.write_concern)

    def test_with_options(self):
        db = self.db
        codec_options = CodecOptions(
            tz_aware=True, uuid_representation=JAVA_LEGACY)

        write_concern = WriteConcern(w=2, j=True)
        db2 = db.with_options(
            codec_options, ReadPreference.SECONDARY, write_concern)

        self.assertTrue(isinstance(db2, AsyncIOMotorDatabase))
        self.assertEqual(codec_options, db2.codec_options)
        self.assertEqual(Secondary(), db2.read_preference)
        self.assertEqual(write_concern, db2.write_concern)

        pref = Secondary([{"dc": "sf"}])
        db2 = db.with_options(read_preference=pref)
        self.assertEqual(pref, db2.read_preference)
        self.assertEqual(db.codec_options, db2.codec_options)
        self.assertEqual(db.write_concern, db2.write_concern)


if __name__ == '__main__':
    unittest.main()
